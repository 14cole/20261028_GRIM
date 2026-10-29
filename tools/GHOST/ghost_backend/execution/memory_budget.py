"""Request-owned RAM accounting; payload, residency and reservations are distinct.

The initial 90% allowance is stable. Live checks price additional allocations
against remaining physical/commit headroom. Weak registrations never keep a
finished operator or factor alive. Scheduler reservations remain hard caps.
"""
from contextlib import contextmanager
import math
import threading
import weakref
from ghost_backend.execution.runtime import ScopedValue

GIB = 1024**3
_STATE = ScopedValue('ghost_request_memory', default=None)
_LOCK = threading.RLock()
_REQUESTS = weakref.WeakSet()


def process_memory():
    try:
        import psutil
        info = psutil.Process().memory_info()
    except Exception:
        from ghost_backend.execution.memory import windows_process_memory
        info = windows_process_memory()
    return (max(0, int(getattr(info, 'rss', 0))),
            getattr(info, 'private', None))


def payload_bytes(value):
    """Currently resident numeric payload, excluding bytes spooled to disk."""
    return max(0, int(getattr(value, 'resident_bytes', getattr(value, 'bytes', 0))))


class MemoryBudget:
    def __init__(self):
        from ghost_backend.twod.solver import _detect_available_gb
        from ghost_backend.execution.memory import windows_available_commit_bytes
        self.initial_available = _detect_available_gb()
        commit = windows_available_commit_bytes()
        self.initial_commit = None if commit is None else commit/GIB
        self.baseline_rss, self.baseline_private = process_memory()
        self.objects = {}
        self.plan = None
        self.ceiling = None
        self.events = []
        self.check_count = 0
        self.last = {}
        self.worker_samples = []

    def register(self, value, kind):
        self.objects[id(value)] = (weakref.ref(value), kind)

    def owned(self):
        numeric = worker_physical = worker_commit = 0
        for key, (ref, kind) in list(self.objects.items()):
            value = ref()
            if value is None:
                self.objects.pop(key, None)
            elif kind == 'workers':
                sample=value.memory_snapshot()
                self.worker_samples.append(sample)
                if len(self.worker_samples)>16:
                    del self.worker_samples[:-16]
                if sample['complete']:
                    worker_physical+=sample['unique_resident_bytes']
                    worker_commit+=sample['private_bytes']
            elif kind == 'factor':
                numeric += payload_bytes(getattr(value, 'factor', None))
            else:
                numeric += payload_bytes(value)
        rss, private = process_memory()
        # Byte ledgers describe arrays, not guaranteed physical residency.
        # Credit no more than the matching process's increase since entry.
        physical = min(numeric, max(0, rss-self.baseline_rss))
        committed = min(numeric, max(0, private-self.baseline_private)) if (
            private is not None and self.baseline_private is not None) else 0
        return numeric/GIB, (physical+worker_physical)/GIB, (committed+worker_commit)/GIB

    def caps(self):
        from ghost_backend.execution.options import allocated_memory_budget, environment_value
        caps = {}
        raw = environment_value('GHOST_MAX_SOLVE_GB', '').strip()
        try:
            explicit = float(raw)
        except ValueError:
            explicit = 0.
        if math.isfinite(explicit) and explicit > 0:
            caps['explicit_ram_budget'] = explicit
        parent = allocated_memory_budget()
        if parent is not None:
            caps['scheduler_reservation'] = parent
        return caps

    def stable(self):
        caps = self.caps()
        if self.ceiling is None:
            initial = dict(caps)
            if self.initial_available is not None:
                initial['initial_physical_ram'] = .9*self.initial_available
            if self.initial_commit is not None:
                initial['initial_commit_headroom'] = .9*self.initial_commit
            ceiling = min(initial.values()) if initial else 0.
            # Concurrent requests in this process must not reserve the same
            # unmaterialized memory. Spawned workers are bounded by their
            # parent scheduler's explicit per-worker reservations instead.
            with _LOCK:
                others=[other for other in _REQUESTS if other is not self and other.ceiling is not None]
                outstanding = sum(max(0., other.ceiling-other.owned()[1]) for other in others)
                reserve=max([.1*(self.initial_available or 0.)]+[
                    .1*(other.initial_available or 0.) for other in others])
                self.ceiling = max(0., min(ceiling,
                    self.initial_available-reserve-outstanding)) if self.initial_available is not None else ceiling
                _REQUESTS.add(self)
        return min([self.ceiling]+list(caps.values()))

    def limit(self, resident_hint=0.):
        from ghost_backend.twod.solver import _detect_available_gb
        from ghost_backend.execution.memory import windows_available_commit_bytes
        stable = self.stable()
        numeric, physical, committed = self.owned()
        available = _detect_available_gb()
        commit = windows_available_commit_bytes()
        physical = max(physical, resident_hint)
        limits = dict(stable_reservation=stable, **self.caps())
        if available is not None:
            reserve = .1*(self.initial_available if self.initial_available is not None else available)
            limits['live_physical_ram'] = physical+max(0., available-reserve)
        else:
            # An explicit cap can support a missing platform probe; absence
            # does not masquerade as a successful zero-memory reading.
            limits['unknown_physical_memory'] = stable if self.caps() else 0.
        if commit is not None:
            reserve = .1*(self.initial_commit if self.initial_commit is not None else commit/GIB)
            limits['live_commit_headroom'] = committed+max(0., commit/GIB-reserve)
        reason = min(limits, key=limits.get)
        self.last = dict(binding_constraint=reason, limit_gib=limits[reason],
            stable_reservation_gib=stable, available_gib=available,
            available_commit_gib=None if commit is None else commit/GIB,
            owned_numeric_gib=numeric, credited_resident_gib=physical,
            credited_commit_gib=committed, limits_gib=limits)
        return max(0., limits[reason])

    def require(self, total_gib, context):
        allowed = self.limit()
        event = dict(self.last, context=context, required_peak_gib=total_gib,
                     admitted=total_gib <= allowed)
        self.events.append(event)
        self.check_count += 1
        if len(self.events)>64:
            del self.events[:-64]
        if total_gib > allowed:
            raise MemoryError('{} requires {:.3f} GiB total; {:.3f} GiB is admitted '
                'by {} (owned payload {:.3f} GiB, available RAM {}).'.format(
                    context,total_gib,allowed,self.last['binding_constraint'],
                    self.last['owned_numeric_gib'],self.last['available_gib']))


@contextmanager
def scope():
    if _STATE.get() is not None:
        yield _STATE.get()
        return
    state = MemoryBudget()
    with _STATE.override(state):
        try:
            yield state
        finally:
            with _LOCK:
                _REQUESTS.discard(state)


def current():
    return _STATE.get()


def register(value, kind='operator'):
    state = current()
    if state is not None:
        state.register(value,kind)


def record_plan(plan):
    state = current()
    if state is not None:
        state.plan = plan


def admit_phase(phase):
    state = current()
    if state is not None and state.plan is not None:
        state.require(state.plan['phase_bytes'][phase]/GIB, 'Compressed '+phase)


def admit_reload(payload, workspace=16*1024**2):
    state = current()
    if state is None:
        from ghost_backend.twod.solver import _solve_memory_limit_gb, _process_rss_bytes
        resident = _process_rss_bytes()/GIB
        if resident+(payload+workspace)/GIB > _solve_memory_limit_gb(resident):
            raise MemoryError('Compressed spool reload exceeds the remaining RAM reservation.')
        return
    # Count the process baseline and all current process allocations in a
    # total reload check, but give live headroom credit only to tracked owners.
    rss, private = process_memory()
    total = max(rss, private or 0)+(payload+workspace)
    state.require(total/GIB, 'Compressed spool reload')


def report():
    state = current()
    if state is None:
        return None
    return dict(policy='90_percent_initial_available_with_live_incremental_checks',
        initial_available_gib=state.initial_available, initial_available_commit_gib=state.initial_commit,
        baseline_rss_bytes=state.baseline_rss, last_check=dict(state.last), checks=list(state.events),
        total_checks=state.check_count, omitted_earlier_checks=max(0,state.check_count-len(state.events)),
        worker_samples=list(state.worker_samples),
        ownership='Weak references to run-owned numeric operators/factors; physical credit is bounded by RSS growth.',
        worker_policy='Scheduler reservations and worker growth allowances remain enforced.')
