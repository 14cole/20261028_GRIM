"""Products that avoid copying a large factor solely to conjugate it."""
import numpy as np


def adjoint_product(a, b):
    """Return a.H @ b, conjugating the smaller operands when that saves work.

    The transpose identity conjugates the RHS and the owned result instead of
    the factor. Keep the direct expression for wide RHS batches, where the
    factor is smaller. Inputs are never modified; strided matrices and vector
    RHS use the same NumPy/BLAS dispatch as ordinary products.
    """
    output_size = a.shape[1] * (1 if b.ndim == 1 else b.shape[1])
    if a.nbytes <= b.nbytes + output_size * np.result_type(a, b).itemsize:
        return a.conj().T @ b
    result = a.T @ b.conj()
    np.conjugate(result, out=result)
    return result
