"""Request-local angle batching for memory admission, without backend selection."""
from contextlib import contextmanager
from ghost_backend.execution.runtime import ScopedValue

_RECOVERY = ScopedValue('ghost_angle_batch_recovery', default=None)


@contextmanager
def scope():
    with _RECOVERY.override(dict(limit=256, events=[])):
        yield


def limit():
    state = _RECOVERY.get()
    return state['limit'] if state is not None else 256


def events():
    state = _RECOVERY.get()
    return state['events'] if state is not None else []


def recover(peak, budget, estimate, available, checkpoint, n_angles, **context):
    """Reprice a compressed system before assembly; never retry a failed solve.

    The caller supplies the actual mesh forecast and the live admission budget,
    including its worker reservation and any permitted resident-memory credit.
    Reductions persist across nested meshes/channels only for this request.
    """
    from ghost_backend.execution.options import option
    from ghost_backend.execution.cpu import configured_batch_size
    state = _RECOVERY.get()
    if peak <= budget or state is None or option('factorization') != 'compressed':
        return peak, budget
    from ghost_backend.compressed.worker_pool import release_idle
    checkpoint()
    requested = configured_batch_size()
    released = release_idle()
    checkpoint()
    peak, budget = estimate(), available()
    attempts = [dict(batch=requested, peak_gib=peak, budget_gib=budget)]
    while peak > budget and configured_batch_size() > 1:
        checkpoint()
        state['limit'] = max(1, min(configured_batch_size()//2, n_angles))
        peak, budget = estimate(), available()
        attempts.append(dict(batch=configured_batch_size(), peak_gib=peak, budget_gib=budget))
    checkpoint()
    event = dict(context, method='compressed_angle_batch_recovery',
        requested_angle_batch_size=requested, angle_batch_size=configured_batch_size(),
        n_angles=n_angles, released_worker_allowance_bytes=released,
        admitted=peak <= budget, attempts=attempts)
    state['events'].append(event)
    return peak, budget
