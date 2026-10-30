"""Incremental inverse-build checks and bounded, request-local observations."""
from contextlib import contextmanager
import weakref
from ghost_backend.execution import memory_budget as mb

MIB = 1024**2


def array_bytes(values):
    # Count backing arrays once, including the unused capacity of views.
    bases = {}
    for value in values:
        if value is None:
            continue
        while getattr(value, 'base', None) is not None and hasattr(value.base, 'nbytes'):
            value = value.base
        bases[id(value)] = int(value.nbytes)
    return sum(bases.values())


class Construction:
    def __init__(self, owner):
        self._owner = weakref.ref(owner)
        self.bytes = 0
        self.evidence = dict(checks=0, live_checks=0, reused_observations=0, largest_increment_bytes=0,
            peak_accounted_build_bytes=0, sampled_process_growth_bytes=0,
            process_samples_exclusive=False, forecast_discount_applied=False)

    @property
    def owner(self):
        return self._owner()

    @contextmanager
    def track(self):
        state = mb.current()
        self.baseline = mb.process_memory()
        if state is not None:
            state.register(self.owner)
            state.register(self)
        try:
            yield self
        finally:
            self.sample()
            self.bytes = 0
            if state is not None:
                with state.object_lock:
                    state.objects.pop(id(self), None)
                    state.objects.pop(id(self.owner), None)

    def sample(self, observation=None):
        rss, private = mb.process_memory() if observation is None else observation
        growth = max(0, rss-self.baseline[0], (private or 0)-(self.baseline[1] or 0))
        self.evidence['sampled_process_growth_bytes'] = max(
            self.evidence['sampled_process_growth_bytes'], growth)
        state = mb.current()
        # Samples can include other work, and miss peaks between checkpoints.
        self.evidence['process_samples_exclusive'] = bool(state is not None and not state.shared_process)

    @contextmanager
    def step(self, label, additional, *live):
        previous = self.bytes
        self.bytes = array_bytes(live)
        additional = int(additional)
        self.owner.checkpoint()
        self.evidence['checks'] += 1
        self.evidence['largest_increment_bytes'] = max(self.evidence['largest_increment_bytes'], additional)
        self.evidence['peak_accounted_build_bytes'] = max(self.evidence['peak_accounted_build_bytes'],
            self.owner.bytes+self.bytes+additional)
        try:
            with mb.construction_allocation(additional, 'Compressed inverse '+label) as observation:
                key = 'live_checks' if observation['live_check'] else 'reused_observations'
                self.evidence[key] += 1
                if observation['process_sample'] is not None:
                    self.sample(observation['process_sample'])
                yield
        finally:
            self.bytes = previous


@contextmanager
def workspace(block, label, additional, *live):
    guard = getattr(block, 'construction', None)
    if guard is None:
        yield
    else:
        with guard.step(label, additional, *live):
            yield


def product_bytes(block, width, adjoint=False):
    estimate = getattr(block, 'product_workspace', None)
    if estimate is not None:
        return estimate(width, adjoint)
    m, n = block.shape
    return 32*MIB + 16*(m+n)*width*4
