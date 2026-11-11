"""R-2 and C-3: factorizations and condition estimates must not touch process-global state."""
import os
import threading
import warnings
from common import *
import scipy.linalg as la
import scipy.sparse.linalg as sla
from ghost_backend.linalg import hierarchical as H
from ghost_backend.linalg.workspace import strict_lu_factor
from ghost_backend.linalg.onenorm import onenormest
from ghost_backend.linalg.refined_lu import RefinedLU

rng = np.random.default_rng(3)

# --- strict_lu_factor equals SciPy and raises on singular input ---------------
A = rng.standard_normal((60, 60)) + 1j * rng.standard_normal((60, 60))
lu, piv = strict_lu_factor(np.array(A, order="F"))
ref_lu, ref_piv = la.lu_factor(A)
check("strict_lu_factor equals scipy.linalg.lu_factor", np.array_equal(lu, ref_lu) and np.array_equal(piv, ref_piv))
singular = A.copy(); singular[:, 5] = 0
check("singular block raises LinAlgError", *raises(lambda: strict_lu_factor(np.array(singular, order="F")), np.linalg.LinAlgError))
check("singular mixed-precision factor raises LinAlgError", *raises(lambda: RefinedLU(singular), np.linalg.LinAlgError))
huge = A * 1e60
check("overflowing single-precision cast raises LinAlgError", *raises(lambda: RefinedLU(huge), np.linalg.LinAlgError))
x = RefinedLU(A).solve(A @ np.ones(60))
check("mixed-precision solve still refines to double", np.max(np.abs(x - 1)) < 1e-10, np.max(np.abs(x - 1)))

# --- concurrent hierarchical factor builds leave the warning filters alone ----
n = 600
pts = np.sort(rng.random(n))
theta = 2 * np.pi * pts
xy = np.c_[np.cos(theta), np.sin(theta)]
dist = np.linalg.norm(xy[:, None] - xy[None, :], axis=2) + np.eye(n)
M = 0.5 * np.eye(n) + np.exp(-8j * dist) / dist / n
old_leaf = H.LEAF_SIZE
H.LEAF_SIZE = 32
H.HierarchicalFactor(M, coordinates=xy)  # warm-up: lazy SciPy imports register their own filters once
before = list(warnings.filters)
caught = []


def victim(stop):
    while not stop.is_set():
        try:
            with np.errstate(divide="warn"):
                np.float64(1.0) / np.float64(0.0)
        except Exception as error:  # a leaked 'error' filter would land here
            caught.append(error)
            return


def builder(out, index):
    try:
        for _ in range(4):
            f = H.HierarchicalFactor(M, coordinates=xy)
            out[index] = np.max(np.abs(M @ f.solve(M @ np.ones(n, complex)) - M @ np.ones(n)))
    except Exception as error:  # noqa: BLE001
        out[index] = error


stop = threading.Event()
out = {}
with warnings.catch_warnings():
    warnings.simplefilter("ignore")  # the victim's warning itself is not under test
    inner = list(warnings.filters)
    v = threading.Thread(target=victim, args=(stop,)); v.start()
    threads = [threading.Thread(target=builder, args=(out, i)) for i in range(3)]
    [t.start() for t in threads]; [t.join() for t in threads]
    stop.set(); v.join()
    check("warning filters unchanged during and after concurrent builds", list(warnings.filters) == inner)
H.LEAF_SIZE = old_leaf
check("no warning became an exception in another thread", not caught, caught[:1])
check("concurrent hierarchical factors solve", all(not isinstance(v, Exception) and v < 1e-8 for v in out.values()), out)
check("filters restored exactly", list(warnings.filters) == before)

# --- private 1-norm estimator ---------------------------------------------------
worst = 1.0
identical = True
for trial in range(120):
    m = int(rng.integers(9, 300))
    B = rng.standard_normal((m, m)) + (1j * rng.standard_normal((m, m)) if trial % 2 else 0)
    if trial % 3 == 0:
        B = np.linalg.inv(B)
    exact = np.max(np.sum(np.abs(B), axis=0))
    np.random.seed(trial)
    position = np.random.get_state()[2]
    mine = onenormest(sla.aslinearoperator(B))
    identical = identical and np.random.get_state()[2] == position
    worst = min(worst, mine / exact)
    if mine > exact * (1 + 1e-12):
        worst = -1
    np.random.seed(0x2D5EED)
    identical = identical and mine == float(sla.onenormest(sla.aslinearoperator(B)))
check("estimator is a lower bound within a factor 2 of the exact 1-norm", 0.5 < worst <= 1.0, "min ratio {:.3f}".format(worst))
check("estimator equals seeded SciPy and leaves the global generator alone", identical)

# --- end to end: compressed condition estimate independent of the caller's seed ---
os.environ["GHOST_HMATRIX_MIN_UNKNOWNS"] = "0"
from ghost_backend.twod import solver as S
a = 0.1
g = scene([("b", 2, "2 1 0 0 0", circle(a, 300)), ("c", 2, "2 1 0 0 0", circle(a, 300, x0=2 * a * 1.005))])
values = {}
for backend in ("compressed", "dense"):
    for seed in (1, 6):
        np.random.seed(seed)
        position = np.random.get_state()[2]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = S.solve_monostatic_rcs_2d(g, [10.0], [0.0, 45.0], geometry_units="meters", compute_condition_number=True,
                                          strict_quality_gate=False,
                                          execution_options=dict(factorization=backend, mesh_strategy="global",
                                                                 assembly_threads=1, blas_threads=1))
        md = r["metadata"]["channel_metadata"]
        values[backend, seed] = (md["VV"]["condition_est_max"], md["HH"]["condition_est_max"], np.random.get_state()[2] == position)
check("compressed estimate independent of seed", values["compressed", 1][:2] == values["compressed", 6][:2], values["compressed", 1][:2])
check("compressed solve leaves the global generator alone", values["compressed", 1][2] and values["compressed", 6][2])
rel = max(abs(values["compressed", 1][i] / values["dense", 1][i] - 1) for i in (0, 1))
check("compressed and dense estimates agree", rel < 1e-6, "relative difference {:.2e}".format(rel))
finish()
