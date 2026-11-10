"""Wall time of fixed 2-D solves for one checkout:  python bench_2d.py <checkout root> [repeats]

Single assembly thread, single BLAS thread, dense LU, fresh process per call
recommended.  Prints the median and the operator-assembly stage per case.
"""
import math
import os
import sys
import time
import warnings

root = os.path.abspath(sys.argv[1])
repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 3
sys.path.insert(0, os.path.join(root, "tools", "GHOST"))
import numpy as np
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
from ghost_backend.twod import solver as S
assert os.path.abspath(S.__file__).startswith(root)


def scene(segments, ibc="", diel=""):
    text = "Title: t\n"
    for name, kind, props, rows in segments:
        text += "Segment: {} {}\nproperties: {}\n{}\n".format(name, kind, props, rows)
    return build_geometry_snapshot(*parse_geometry(text + "IBCS_Resistances:\n{}\nDielectrics:\n{}\n".format(ibc, diel)))


def circle(radius, count, sliver=False):
    theta = list(-np.linspace(0, 2 * np.pi, count + 1))
    if sliver:  # split one panel, leaving a piece 5e-4 of a panel long
        theta.insert(1, theta[0] + (theta[1] - theta[0]) * 5e-4)
    pts = [(radius * math.cos(t), radius * math.sin(t)) for t in theta]
    pts[-1] = pts[0]
    return "\n".join("{:.15g} {:.15g} {:.15g} {:.15g}".format(*pts[i], *pts[i + 1]) for i in range(len(pts) - 1))


def freq(radius, count, kl):  # frequency (GHz) giving |k| L = kl on the polygon
    return kl / (2 * math.pi * radius / count) * 0.299792458 / (2 * math.pi)


CASES = {
    "pec_1600_kL0.31": (scene([("b", 2, "2 1 0 0 0", circle(0.5, 1600))]), freq(0.5, 1600, 0.31)),
    "ibc_1600_kL0.31": (scene([("b", 2, "2 1 10 0 0", circle(0.5, 1600))], ibc="10 constant 75 -20 0 0"), freq(0.5, 1600, 0.31)),
    "ibc_1600_kL1.0": (scene([("b", 2, "2 1 10 0 0", circle(0.5, 1600))], ibc="10 constant 75 -20 0 0"), freq(0.5, 1600, 1.0)),
    "coated_800+560": (scene([("o", 3, "3 1 0 1 0", circle(0.5, 800)), ("c", 4, "4 1 0 1 0", circle(0.35, 560))], diel="1 3.0 -0.06 1.0 0.0"), freq(0.5, 800, 0.18)),
    "ibc_1200_one_sliver": (scene([("b", 2, "2 1 10 0 0", circle(0.5, 1200, sliver=True))], ibc="10 constant 75 -20 0 0"), freq(0.5, 1200, 0.31)),
    "ibc_1200_no_sliver": (scene([("b", 2, "2 1 10 0 0", circle(0.5, 1200))], ibc="10 constant 75 -20 0 0"), freq(0.5, 1200, 0.31)),
}
only = sys.argv[3:] or list(CASES)
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    for name in only:
        g, f = CASES[name]
        walls, stages = [], []
        for _ in range(repeats):
            start = time.perf_counter()
            r = S.solve_monostatic_rcs_2d(g, [f], [0.0, 45.0, 90.0], geometry_units="meters",
                                          execution_options=dict(factorization="dense", assembly_threads=1, blas_threads=1,
                                                                 mesh_strategy="global"))
            walls.append(time.perf_counter() - start)
            stages.append(r["metadata"]["runtime_profile"]["stage_seconds"].get("operators", float("nan")))
        print("{:<22} wall median {:.3f} s (min {:.3f})  operators median {:.3f} s".format(
            name, float(np.median(walls)), min(walls), float(np.median(stages))), flush=True)
