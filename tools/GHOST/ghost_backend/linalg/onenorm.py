"""Block 1-norm estimator with private randomness.

``scipy.sparse.linalg.onenormest`` draws its second probe column from NumPy's
process-global generator.  An estimate then depends on whatever the caller (or
another thread) drew before, and the caller's stream is advanced.  Reseeding
the global generator around the call hides that from one thread only.  This
estimator follows the same published algorithm (Higham and Tisseur, "A block
algorithm for matrix 1-norm estimation", SIAM J. Matrix Anal. Appl. 21 (2000),
Algorithm 2.4) with a generator it owns, so a given operator always returns
the same value and no global state is read or written.

The value is a lower bound of the 1-norm: every candidate is the 1-norm of the
operator applied to a vector of unit 1-norm.
"""
import numpy as np


SEED = 0x2D5EED


def _signs(values):
    """Unit-modulus signs, with 1 where the entry is zero."""
    magnitude = np.abs(values)
    return np.where(magnitude > 0, values / np.where(magnitude > 0, magnitude, 1.0), 1.0)


def _parallel(column, others):
    """A +-1 real column is parallel to one of ``others`` (columns of +-1)."""
    if others is None or not others.shape[1]:
        return False
    return bool(np.any(np.abs(others.T @ column) == len(column)))


def onenormest(operator, t=2, itmax=5, seed=SEED):
    """Estimated 1-norm of a square linear operator (matmat and rmatmat)."""
    n = operator.shape[0]
    if operator.shape[0] != operator.shape[1]:
        raise ValueError('The operator must be square.')
    if n == 0:
        return 0.0
    t = max(1, min(int(t), n))
    if n <= 4 * t:
        # Small systems: the exact norm costs no more than the estimate.
        columns = np.asarray(operator.matmat(np.eye(n, dtype=complex)))
        return float(np.max(np.sum(np.abs(columns), axis=0)))
    rng = np.random.RandomState(seed)
    x = np.ones((n, t), dtype=float)
    if t > 1:
        x[:, 1:] = rng.randint(0, 2, size=(n, t - 1)) * 2 - 1
        for j in range(1, t):
            while _parallel(x[:, j], x[:, :j]):
                x[:, j] = rng.randint(0, 2, size=n) * 2 - 1
    x /= n
    history = np.zeros(n, dtype=bool)
    indices = np.arange(t)
    estimate_old = 0.0
    signs_old = None
    best = 0
    k = 1
    while True:
        y = np.asarray(operator.matmat(x.astype(complex)))
        norms = np.sum(np.abs(y), axis=0)
        j = int(np.argmax(norms))
        estimate = float(norms[j])
        if estimate > estimate_old or k == 2:
            if k >= 2:
                best = int(indices[j])
        if k >= 2 and estimate <= estimate_old:
            estimate = estimate_old
            break
        estimate_old = estimate
        if k > itmax:
            break
        signs = _signs(y)
        if np.isrealobj(signs) or not np.any(signs.imag):
            real = np.sign(signs.real)
            real[real == 0] = 1
            # Real signs: stop when nothing new would be probed, and replace
            # columns that repeat an earlier probe.
            if signs_old is not None and all(_parallel(real[:, c], signs_old) for c in range(t)):
                break
            if t > 1:
                for c in range(t):
                    others = real[:, :c] if signs_old is None else np.hstack((real[:, :c], signs_old))
                    while _parallel(real[:, c], others):
                        real[:, c] = rng.randint(0, 2, size=n) * 2 - 1
            signs_old = real
            signs = real.astype(complex)
        z = np.asarray(operator.rmatmat(signs))
        h = np.max(np.abs(z), axis=1)
        if k >= 2 and np.max(h) == h[best]:
            break
        order = np.argsort(-h, kind='stable')
        if t > 1:
            if np.all(history[order[:t]]):
                break
            fresh = order[~history[order]]
            order = np.concatenate((fresh, order[history[order]]))
        indices = order[:t]
        x = np.zeros((n, t), dtype=float)
        x[indices, np.arange(t)] = 1.0
        history[indices] = True
        k += 1
    return float(estimate)
