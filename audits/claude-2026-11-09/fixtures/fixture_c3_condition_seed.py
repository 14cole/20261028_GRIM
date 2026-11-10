"""C-3 fixture: compressed condition estimate vs NumPy global seed.

Two PEC polygon circles (radius 0.1 m, 600 panels each, centre spacing 0.201 m),
10 GHz, co-polarised call. Run from the repository root:
    python fixture_c3_condition_seed.py tile     # compressed tile backend
    python fixture_c3_condition_seed.py lu       # dense LU
onenormest returns a lower bound of the 1-norm, so for a fixed matrix every
value printed is a lower bound of the same quantity; the largest is the best.
"""
import math, os, sys, warnings
sys.path.insert(0, os.path.join(os.getcwd(), "tools", "GHOST"))
import numpy as np
backend = sys.argv[1]
opts = dict(mesh_strategy="global", assembly_threads=1, blas_threads=1)
if backend == "lu":
    opts["factorization"] = "dense"; os.environ["GHOST_HIERARCHICAL_MIN_UNKNOWNS"] = "0"
else:
    opts["factorization"] = "compressed"; os.environ["GHOST_HMATRIX_MIN_UNKNOWNS"] = "0"
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
from ghost_backend.twod import solver as S

def rows(a, n, x0=0.0):
    th = -np.linspace(0, 2 * np.pi, n + 1)
    r = a * math.sqrt((2 * math.pi / n) / math.sin(2 * math.pi / n))
    x = x0 + r * np.cos(th); y = r * np.sin(th)
    return "\n".join(f"{x[i]:.15g} {y[i]:.15g} {x[i+1]:.15g} {y[i+1]:.15g}" for i in range(n))

a = 0.1
g = build_geometry_snapshot(*parse_geometry(
    f"Title: t\nSegment: b 2\nproperties: 2 1 0 0 0\n{rows(a, 600)}\n"
    f"Segment: c 2\nproperties: 2 1 0 0 0\n{rows(a, 600, 2 * a * 1.005)}\n"
    "IBCS_Resistances:\nDielectrics:\n"))
for seed in (1, 2, 3, 4, 5, 6):
    np.random.seed(seed); pos = np.random.get_state()[2]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = S.solve_monostatic_rcs_2d(g, [10.0], [0.0, 45.0], geometry_units="meters",
                                      compute_condition_number=True, strict_quality_gate=False,
                                      execution_options=opts)
    md = r["metadata"]["channel_metadata"]
    print(backend, "seed", seed, "cond VV %.8g HH %.8g" % (md["VV"]["condition_est_max"], md["HH"]["condition_est_max"]),
          md["HH"]["condition_estimator"], "rng pos", pos, "->", np.random.get_state()[2], flush=True)
