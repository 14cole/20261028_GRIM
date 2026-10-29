"""Request-owned RAM accounting; payload, residency and reservations are distinct.

The initial physical allowance is stable. Verified OS commit-limit growth can
expand a commit-limited reservation within that physical allowance. Live checks price additional allocations
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
        from ghost_backend.execution.memory import windows_available_commit_bytes, windows_system_commit
        self.initial_available = _detect_available_gb()
        commit = windows_available_commit_bytes()
        self.initial_commit = None if commit is None else commit/GIB
        self.initial_system_commit = windows_system_commit()
        if self.initial_commit is not None and self.initial_system_commit is not None:
            system_available = max(0, self.initial_system_commit['limit_bytes']-
                self.initial_system_commit['committed_bytes'])/GIB
            self.initial_commit = min(self.initial_commit, system_available)
        self.last_system_commit = self.initial_system_commit
        self.baseline_rss, self.baseline_private = process_memory()
        self.objects = {}
        self.plan = None
        self.ceiling = None
        self.reservation_limits = {}
        self.initial_caps = None
        self.events = []
        self.check_count = 0
        self.last = {}
        self.worker_samples = []
        self.worker_ownership = (0., 0.)
        self.shared_process = False
        self.cohort = None
        self.object_lock = threading.RLock()

    def register(self, value, kind='operator'):
        with self.object_lock:
            self.objects[id(value)] = (weakref.ref(value), kind)

    def owned(self):
        numeric = worker_physical = worker_commit = 0
        with self.object_lock:
            objects = list(self.objects.items())
        for key, (ref, kind) in objects:
            value = ref()
            if value is None:
                with self.object_lock:
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
        with _LOCK:
            physical = 0 if self.shared_process else min(numeric, max(0, rss-self.baseline_rss))
            committed = min(numeric, max(0, private-self.baseline_private)) if (
                not self.shared_process and private is not None and self.baseline_private is not None) else 0
        self.worker_ownership = (worker_physical/GIB, worker_commit/GIB)
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

    def enrol(self):
        with _LOCK:
            if self.cohort is None:
                others = list(_REQUESTS)
                if others:
                    self.cohort = others[0].cohort
                    self.shared_process = True
                    for other in others:
                        other.shared_process = True
                else:
                    hardware = []
                    if self.initial_available is not None:
                        hardware.append(.9*self.initial_available)
                    if self.initial_commit is not None:
                        hardware.append(.9*self.initial_commit)
                    self.cohort = dict(capacity=min(hardware) if hardware else None,
                        initial_physical_capacity=None if self.initial_available is None else .9*self.initial_available,
                        initial_commit=self.initial_commit, initial_system_commit=self.initial_system_commit,
                        system_commit=self.initial_system_commit, commit_capacity_changes=[],
                        physical_reserve=.1*(self.initial_available or 0.),
                        commit_reserve=.1*(self.initial_commit or 0.))
                _REQUESTS.add(self)

    def stable(self):
        from ghost_backend.execution.memory import windows_system_commit
        caps = self.caps()
        self.enrol()
        with _LOCK:
            observation = windows_system_commit()
            if observation is not None:
                self.last_system_commit = observation
                group = self.cohort
                original = group['initial_system_commit']
                if (original is not None and group['initial_commit'] is not None
                        and group['initial_physical_capacity'] is not None):
                    # Only growth of the actual OS backing limit creates new
                    # capacity. Freeing other apps' memory or our own arrays
                    # cannot enlarge the group's reservations.
                    delta = (observation['limit_bytes']-original['limit_bytes'])/GIB
                    commit_allowance = max(0., group['initial_commit']+delta)
                    capacity = min(group['initial_physical_capacity'], .9*commit_allowance)
                    if capacity != group['capacity']:
                        group['commit_capacity_changes'].append(dict(previous_gib=group['capacity'],
                            capacity_gib=capacity, system_commit=dict(observation)))
                        del group['commit_capacity_changes'][:-16]
                    group.update(capacity=capacity, system_commit=observation,
                        commit_reserve=.1*commit_allowance)
            # An unknown host probe can still use a subsequently supplied cap.
            if self.cohort['capacity'] is None:
                self.cohort['capacity'] = min(caps.values(), default=0.)
            if self.initial_caps is None:
                self.initial_caps = dict(caps)
            initial = dict(self.initial_caps)
            for key, value in caps.items():
                initial[key] = min(initial.get(key, value), value)
            if self.initial_available is not None:
                initial['initial_physical_ram'] = .9*self.initial_available
            if self.initial_commit is not None:
                delta = 0.
                observed = self.last_system_commit
                if observed is not None and self.initial_system_commit is not None and self.initial_available is not None:
                    delta = (observed['limit_bytes']-self.initial_system_commit['limit_bytes'])/GIB
                name = 'verified_system_commit_capacity' if delta else 'initial_commit_headroom'
                initial[name] = .9*max(0., self.initial_commit+delta)
            # Keep the aggregate reservation fixed for the overlapping cohort.
            # Materialized pages do not create new reservation capacity, and
            # admission never samples or mutates another request's telemetry.
            reserved = sum(other.ceiling or 0. for other in _REQUESTS if other is not self)
            initial['cohort_remaining_reservation'] = max(0., self.cohort['capacity']-reserved)
            self.reservation_limits = initial
            admitted = max(0., min(initial.values()))
            # Keep previously promised bytes reserved after a cap tightens or
            # the OS backing limit contracts. They may already be allocated;
            # lowering the held reservation would let a peer spend them again.
            self.ceiling = max(self.ceiling or 0., admitted)
        return admitted

    def baseline_credit(self):
        # Only the interpreter baseline explicitly present in the forecast is
        # already paid for. Geometry, cache capacities and workspaces can grow.
        baseline = (self.plan or {}).get('process_baseline_bytes', 0)
        with _LOCK:
            if self.shared_process:
                return 0., 0.
        return min(baseline, self.baseline_rss)/GIB, min(baseline, self.baseline_private or 0)/GIB

    def limit(self, resident_hint=0.):
        from ghost_backend.twod.solver import _detect_available_gb
        from ghost_backend.execution.memory import windows_available_commit_bytes
        stable = self.stable()
        numeric, physical, committed = self.owned()
        available = _detect_available_gb()
        commit = windows_available_commit_bytes()
        baseline_physical, baseline_commit = self.baseline_credit()
        physical += baseline_physical
        committed += baseline_commit
        # Legacy whole-process hints have no exclusive owner during overlap.
        if not self.shared_process:
            physical = max(physical, resident_hint)
        limits = dict(stable_reservation=stable, **self.caps())
        if available is not None:
            reserve = max(self.cohort['physical_reserve'], .1*(self.initial_available or 0.))
            limits['live_physical_ram'] = physical+max(0., available-reserve)
        else:
            # An explicit cap can support a missing platform probe; absence
            # does not masquerade as a successful zero-memory reading.
            limits['unknown_physical_memory'] = stable if self.caps() else 0.
        if commit is not None:
            reserve = max(self.cohort['commit_reserve'], .1*(self.initial_commit or 0.))
            limits['live_commit_headroom'] = committed+max(0., commit/GIB-reserve)
        reason = min(limits, key=limits.get)
        reservation_constraints = dict(self.reservation_limits)
        for key, value in self.caps().items():
            reservation_constraints[key] = min(reservation_constraints.get(key, value), value)
        self.last = dict(binding_constraint=reason, limit_gib=limits[reason],
            stable_reservation_gib=stable, available_gib=available,
            reservation_constraints_gib=reservation_constraints,
            reservation_binding_constraint=min(reservation_constraints, key=reservation_constraints.get),
            available_commit_gib=None if commit is None else commit/GIB,
            system_commit=self.last_system_commit,
            owned_numeric_gib=numeric, credited_resident_gib=physical,
            owned_worker_resident_gib=self.worker_ownership[0],
            owned_worker_commit_gib=self.worker_ownership[1],
            credited_commit_gib=committed, limits_gib=limits)
        return max(0., limits[reason])

    def _check(self, total_gib, allowed, context, **details):
        event = dict(self.last, context=context, required_peak_gib=total_gib,
                     admitted=total_gib <= allowed, **details)
        self.events.append(event)
        self.check_count += 1
        if len(self.events)>64:
            del self.events[:-64]
        if total_gib > allowed:
            units = 'additional allocation' if 'additional_allocation_gib' in details else 'total'
            reason = self.last['binding_constraint']
            if reason == 'stable_reservation':
                reason += ' (set by {})'.format(self.last['reservation_binding_constraint'])
            raise MemoryError('{} requires {:.3f} GiB {}; {:.3f} GiB is admitted '
                'by {} (owned payload {:.3f} GiB, available RAM {}).'.format(
                    context,total_gib,units,allowed,reason,
                    self.last['owned_numeric_gib'],self.last['available_gib']))

    def require(self, total_gib, context):
        self._check(total_gib, self.limit(), context)

    def require_reload(self, additional_bytes):
        """Check new physical/commit allocations separately from total ownership."""
        self.limit()
        numeric = self.last['owned_numeric_gib']
        overhead = (self.plan or {}).get('process_geometry_bytes', 0)/GIB
        worker_physical, worker_commit = self.worker_ownership
        resident = numeric+max(overhead, worker_physical, worker_commit)
        if not self.shared_process:
            rss, private = process_memory()
            resident = max(resident, max(0, rss-self.baseline_rss)/GIB+worker_physical,
                max(0, (private or 0)-(self.baseline_private or 0))/GIB+worker_commit)
        extra = additional_bytes/GIB
        limits = dict(stable_reservation=max(0., self.stable()-resident))
        available = self.last['available_gib']
        if available is not None:
            limits['live_physical_ram'] = max(0., available-max(
                self.cohort['physical_reserve'], .1*(self.initial_available or 0.)))
        elif not self.caps():
            limits['unknown_physical_memory'] = 0.
        commit = self.last['available_commit_gib']
        if commit is not None:
            limits['live_commit_headroom'] = max(0., commit-max(
                self.cohort['commit_reserve'], .1*(self.initial_commit or 0.)))
        reason = min(limits, key=limits.get)
        self.last.update(binding_constraint=reason, limit_gib=limits[reason],
            limits_gib=limits, check_units='additional_allocation_gib')
        self._check(extra, limits[reason], 'Compressed spool reload',
            additional_allocation_gib=extra, reserved_usage_after_reload_gib=resident+extra)


@contextmanager
def scope():
    if _STATE.get() is not None:
        yield _STATE.get()
        return
    state = MemoryBudget()
    # Enrol immediately so allocations made before the first forecast cannot
    # later be attributed exclusively to another overlapping request.
    state.enrol()
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
        allowed = state.limit()
        peak = state.plan['phase_bytes'][phase]/GIB
        nonstorage = state.plan.get('nonstorage_phase_bytes', {}).get(phase)
        if nonstorage is not None:
            peak = max(peak, state.last['owned_numeric_gib']+nonstorage/GIB)
        state._check(peak, allowed, 'Compressed '+phase)


def admit_reload(payload, workspace=16*1024**2):
    state = current()
    if state is None:
        from ghost_backend.twod.solver import _solve_memory_limit_gb, _process_rss_bytes
        resident = _process_rss_bytes()/GIB
        if resident+(payload+workspace)/GIB > _solve_memory_limit_gb(resident):
            raise MemoryError('Compressed spool reload exceeds the remaining RAM reservation.')
        return
    state.require_reload(payload+workspace)


def report():
    state = current()
    if state is None:
        return None
    return dict(policy='90_percent_initial_available_with_live_incremental_checks',
        initial_available_gib=state.initial_available, initial_available_commit_gib=state.initial_commit,
        baseline_rss_bytes=state.baseline_rss, last_check=dict(state.last), checks=list(state.events),
        total_checks=state.check_count, omitted_earlier_checks=max(0,state.check_count-len(state.events)),
        worker_samples=list(state.worker_samples),
        shared_process=state.shared_process, cohort_capacity_gib=state.cohort['capacity'],
        initial_system_commit=state.initial_system_commit,
        commit_capacity_changes=list(state.cohort['commit_capacity_changes']),
        commit_policy='Expand only after observed system backing-limit growth; initial physical/user/scheduler caps and live checks still apply.',
        ownership='Weak run-owned references; no parent-process growth credit after request overlap.',
        worker_policy='Scheduler reservations and worker growth allowances remain enforced.')
