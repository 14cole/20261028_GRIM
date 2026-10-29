"""Request-owned inverse-accuracy hints; no retained matrices or cross-run state."""
from contextlib import contextmanager
import math
import threading
import hashlib
import json
from ghost_backend.execution.runtime import ScopedValue

_CURRENT = ScopedValue('ghost_preconditioner_hints', None)


@contextmanager
def scope(frequencies, geometry=None, material_base_dir=None, geometry_units=None):
    # Nested adaptive/polarization solves inherit the outer request. A sweep
    # deliberately disables sharing rather than transfer learning across k.
    physical = ({k:v for k,v in geometry.items() if not k.startswith('_2d_hp_')}
                if isinstance(geometry, dict) else geometry)
    identity = hashlib.sha256(json.dumps([list(frequencies), physical, material_base_dir, geometry_units],
        sort_keys=True, default=str).encode('utf-8')).digest()
    if _CURRENT.get() is not None and _CURRENT.get()['identity'] == identity:
        yield
        return
    state = dict(identity=identity, enabled=len(frequencies) == 1, entries={}, lock=threading.RLock())
    with _CURRENT.override(state):
        yield


def _key(factor):
    state = _CURRENT.get()
    if state is None or not state['enabled'] or factor.a.evidence.get('operator') != 'hmatrix':
        return None
    from ghost_backend.execution.cpu import current_state
    cpu = current_state()
    formulation = getattr(cpu, 'current_resources', {}).get('formulation')
    if not formulation:
        return None
    oracle = factor.a.oracle
    return (type(factor).__name__, type(oracle).__name__, formulation, getattr(oracle, 'kind', None))


def remember(factor):
    """Called only after a field inverse passes physical and sample-row gates."""
    from ghost_backend.compressed.factor import UPGRADED_PRECONDITIONER_TOLERANCE
    key = _key(factor)
    if key is None or factor.tolerance > UPGRADED_PRECONDITIONER_TOLERANCE:
        return
    state = _CURRENT.get()
    with state['lock']:
        if key not in state['entries'] and len(state['entries']) >= 16:
            return
        state['entries'][key] = dict(unknowns=factor.a.n, bytes=int(factor.factor.bytes))


def discard(factor):
    key = _key(factor)
    if key is not None:
        state = _CURRENT.get()
        with state['lock']:
            state['entries'].pop(key, None)


def try_build(factor):
    """Admit an optional stronger initial build, falling back on any rejection."""
    key = _key(factor)
    if key is None or getattr(factor, '_hint_attempted', False):
        return False
    state = _CURRENT.get()
    with state['lock']:
        previous = state['entries'].get(key)
    if previous is None:
        return False
    factor._hint_attempted = True
    from ghost_backend.twod.solver import _process_rss_bytes, _solve_memory_limit_gb
    from ghost_backend.compressed.worker_pool import retained_bytes
    from ghost_backend.compressed.factor import UPGRADED_PRECONDITIONER_TOLERANCE
    from ghost_backend.linalg.hierarchical import HierarchicalRejected
    import numpy as np
    # Quadratic growth is deliberately conservative for an adaptive size change;
    # it is a reservation heuristic, not a rank/memory prediction guarantee.
    predicted = int(math.ceil(previous['bytes'] * max(1., factor.a.n/previous['unknowns'])**2))
    allowance = 2*predicted
    construction = max(64*1024**2, 3*predicted)
    resident = _process_rss_bytes() + retained_bytes()
    available = max(0, int(_solve_memory_limit_gb(resident/1024**3)*1024**3-resident))
    event = dict(source='validated_field_solve_in_same_single_frequency_request',
        reference_unknowns=previous['unknowns'], reference_inverse_bytes=previous['bytes'],
        predicted_inverse_bytes=predicted, payload_allowance_bytes=allowance,
        construction_allowance_bytes=construction, available_bytes=available, accepted=False)
    factor.event['preconditioner_hint'] = event
    if factor.budget < allowance or available < construction:
        event['reason'] = 'insufficient replacement construction or payload headroom'
        return False
    budget = factor.budget
    factor.budget = min(budget, allowance)
    failed = False
    try:
        factor._build(UPGRADED_PRECONDITIONER_TOLERANCE)
    except (MemoryError, HierarchicalRejected, np.linalg.LinAlgError, RuntimeWarning) as exc:
        event['reason'] = '{}: {}'.format(type(exc).__name__, exc)
        failed = True
    except BaseException:
        factor.factor = None
        raise
    finally:
        factor.budget = budget
    if failed:
        # Leave the handler first so the rejected tree's traceback is released.
        factor.factor = None
        with state['lock']:
            state['entries'].pop(key, None)
        return False
    event.update(accepted=True, inverse_bytes=int(factor.factor.bytes), tolerance=factor.tolerance)
    return True
