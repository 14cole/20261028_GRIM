"""Research wrapper: normalize components before shared-skeleton compression.

Zero sampled components stay in the row/column probe tests. They are never
declared identically zero or dropped. Finite failures reject to exact storage.
The stopping test is sampled, not a certified bound for unseen coefficients.
"""
import numpy as np
from ghost_backend.compressed.hmatrix import cross_approximation, HMatrixRejected


def scaled_components(fetch, shape, tolerance, rng, max_rank):
    m, n = shape
    if not np.isfinite(tolerance) or not 0 < tolerance < 1:
        raise ValueError('Compression tolerance must be finite and in (0,1)')
    sample = np.unique(np.linspace(0, m-1, min(8, m), dtype=int))
    values = fetch(sample, None)
    scales = []
    for value in values:
        if not np.all(np.isfinite(value)):
            raise HMatrixRejected('Nonfinite compression sample')
        # Max scaling avoids squaring tiny physical coefficients in the norm.
        largest = max(np.max(abs(value.real)), np.max(abs(value.imag)))
        if largest:
            if largest < np.finfo(float).tiny:
                # Factoring then rescaling such data can lose the requested
                # relative accuracy even when normalized arithmetic is finite.
                raise HMatrixRejected('Subnormal component needs exact storage')
            normalized = value.real/largest + 1j*(value.imag/largest)
            scale = largest * np.linalg.norm(normalized) * np.sqrt(m/len(sample))
        else:
            scale = 1.0
        if not np.isfinite(scale) or scale <= 0:
            raise HMatrixRejected('Unrepresentable component scale')
        scales.append(scale)

    def query(rows=None, cols=None):
        answer = []
        for value, scale in zip(fetch(rows, cols), scales):
            # Complex division by a subnormal real can form 0*inf internally.
            normalized = value.real/scale + 1j*(value.imag/scale)
            if not np.all(np.isfinite(normalized)):
                raise HMatrixRejected('Nonfinite normalized coefficients')
            answer.append(normalized)
        return answer

    try:
        with np.errstate(invalid='raise', divide='raise', over='raise'):
            factors, estimate = cross_approximation(
                lambda r: query(r, None), lambda c: query(None, c),
                shape, [tolerance]*len(scales), 8, rng, max_rank=max_rank)
            result = [(u*scale, v) for (u, v), scale in zip(factors, scales)]
        if not np.isfinite(estimate) or any(not np.all(np.isfinite(a)) for f in result for a in f):
            raise HMatrixRejected('Nonfinite compression result')
        return result, estimate
    except FloatingPointError as exc:
        raise HMatrixRejected('Unsafe floating-point compression') from exc
