"""C-2: DenseFactor.solve must reject nonfinite solutions and keep valid zero right-hand sides."""
import warnings
from common import *
from ghost_backend.linalg.dense import DenseFactor

rng = np.random.default_rng(0)
n = 200
A = rng.standard_normal((n, n)) + 1j * rng.standard_normal((n, n))
b = rng.standard_normal((n, 3)) + 0j


def solve(matrix, rhs):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        factor = DenseFactor(np.array(matrix, dtype=complex, order="F"), None, "t")
        return factor, factor.solve(rhs)


zero_col = A.copy(); zero_col[:, 7] = 0
check("zero column rejected", *raises(lambda: solve(zero_col, b), RuntimeError))
check("zero matrix rejected", *raises(lambda: solve(np.zeros((n, n)), b), RuntimeError))
check("diagonal with a zero rejected", *raises(lambda: solve(np.diag(np.r_[np.ones(n - 1), 0.0]), b), RuntimeError))
check("3x3 zero system rejected", *raises(lambda: solve(np.zeros((3, 3)), np.ones((3, 1))), RuntimeError))

f, x = solve(np.eye(3), np.zeros((3, 1), complex))
check("A=I, b=0 accepted with x=0", np.array_equal(x, np.zeros((3, 1))) and f.event["max_backward_error"] == 0.0)
f, x = solve(A, np.zeros((n, 2), complex))
check("random A, b=0 accepted with x=0", not np.any(x) and f.event["max_backward_error"] == 0.0)
mixed = b.copy(); mixed[:, 1] = 0
f, x = solve(A, mixed)
check("zero column among nonzero RHS accepted", np.all(np.isfinite(x)) and not np.any(x[:, 1]) and f.event["max_backward_error"] < 1e-13,
      f.event["max_backward_error"])
f, x = solve(A, b)
err = np.max(np.abs(A @ x - b)) / (np.max(np.sum(np.abs(A), axis=1)) * np.max(np.abs(x)) + np.max(np.abs(b)))
check("regular system unchanged", err < 1e-14 and f.event["max_backward_error"] < 1e-14, "backward {:.2e}".format(err))
f, x = solve(A, b[:, 0])
check("vector RHS keeps its shape", x.shape == (n,))
finish()
