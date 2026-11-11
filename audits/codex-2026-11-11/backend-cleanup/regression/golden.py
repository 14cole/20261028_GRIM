"""Before/after field comparison.

    python golden.py <path to a GHOST checkout root> <out.npz>     # compute
    python golden.py --compare <a.npz> <b.npz>                      # compare

The cases cover every 2-D formulation family and the BoR conductor, impedance,
dielectric, coated and sheet solvers.  Values are complex amplitudes (2-D) and
linear RCS (BoR) in request order.
"""
import math
import os
import sys
import warnings

import numpy as np


def compare(a_path, b_path):
    a, b = np.load(a_path), np.load(b_path)
    worst = 0.0
    for key in a.files:
        if key not in b.files:
            print("MISSING", key)
            worst = math.inf
            continue
        scale = np.max(np.abs(a[key]))
        diff = float(np.max(np.abs(a[key] - b[key])) / scale) if scale else 0.0
        worst = max(worst, diff)
        print("{:<34} {} max relative difference {:.3e}".format(
            key, "bitwise" if np.array_equal(a[key], b[key]) else "       ", diff))
    print("worst {:.3e}".format(worst))
    return worst


if sys.argv[1] == "--compare":
    compare(sys.argv[2], sys.argv[3])
    sys.exit(0)

root, out = os.path.abspath(sys.argv[1]), sys.argv[2]
sys.path.insert(0, os.path.join(root, "tools", "GHOST"))
here = os.path.dirname(os.path.abspath(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location("golden_common", os.path.join(here, "common.py"))
# common.py inserts its own checkout first; the requested root must win.
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
sys.path.insert(0, os.path.join(root, "tools", "GHOST"))
for name in [m for m in sys.modules if m.startswith("ghost_backend")]:
    del sys.modules[name]
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
from ghost_backend.twod import solver as S
from ghost_backend.bor import dispatch as D
assert os.path.abspath(S.__file__).startswith(root) and os.path.abspath(D.__file__).startswith(root), S.__file__
common.build_geometry_snapshot, common.parse_geometry = build_geometry_snapshot, parse_geometry
scene, circle, rect, rows, arc, bor_sphere = common.scene, common.circle, common.rect, common.rows, common.arc, common.bor_sphere

ANG = [0.0, 37.0, 90.0, 201.0]
D1 = "1 4.0 -0.2 1.0 0.0"
TWOD = {
    "pec_circle": (scene([("b", 2, "2 1 0 0 0", circle(0.1, 240))]), 3.0),
    "ibc_circle": (scene([("b", 2, "2 1 10 0 0", circle(0.1, 240))], ibc="10 constant 50 -200 0 0"), 3.0),
    "pec_ibc_zones": (scene([("a", 2, "2 -20 0 0 0", arc(0.05, math.pi, 0.0, 24)), ("b", 2, "2 -20 10 0 0", arc(0.05, 0.0, -math.pi, 24))], ibc="10 constant 75 -20 0 0"), 3.0),
    "pec_square": (scene([("b", 2, "2 0 0 0 0", rect(-0.05, -0.05, 0.05, 0.05))]), 3.0),
    "dielectric_circle": (scene([("b", 3, "3 1 0 1 0", circle(0.1, 240))], diel=D1), 2.0),
    "dielectric_square": (scene([("b", 3, "3 0 0 1 0", rect(-0.05, -0.05, 0.05, 0.05))], diel=D1), 2.0),
    "coated_pec": (scene([("o", 3, "3 1 0 1 0", circle(0.1, 240)), ("c", 4, "4 1 0 1 0", circle(0.07, 168))], diel="1 3.0 -0.06 1.2 -0.1"), 2.0),
    "two_layer": (scene([("o", 3, "3 1 0 1 0", circle(0.1, 240)), ("c", 5, "5 1 0 1 2", circle(0.06, 144))], diel="1 2.5 -0.05 1.0 0.0\n2 6.0 -0.3 1.0 0.0"), 2.0),
    "partial_coating": (scene([("bare", 2, "2 0 0 0 0", arc(0.07, math.pi, 0.0, 40)), ("core", 4, "4 0 0 1 0", arc(0.07, 0.0, -math.pi, 40)),
                               ("coat", 3, "3 0 0 1 0", rows([(0.07, 0.0), (0.1, 0.0)]) + "\n" + arc(0.1, 0.0, -math.pi, 56) + "\n" + rows([(-0.1, 0.0), (-0.07, 0.0)]))], diel="1 3.0 0.0 1.0 0.0"), 1.5),
    "sheet": (scene([("s", 1, "1 -20 10 0 0", rows([(-0.1, 0.0), (0.1, 0.0)]))], ibc="10 constant 150 60 0 0"), 2.0),
    "sheet_plus_pec": (scene([("s", 1, "1 -20 10 0 0", rows([(-0.05, -0.08), (0.05, -0.08)])), ("b", 2, "2 -20 0 0 0", rect(-0.05, 0.0, 0.05, 0.05))], ibc="10 constant 150 60 0 0"), 2.0),
    "two_pec_bodies": (scene([("b", 2, "2 1 0 0 0", circle(0.05, 120)), ("c", 2, "2 1 0 0 0", circle(0.05, 120, x0=0.1005))]), 4.0),
}
BOR = {
    "bor_pec_sphere": (scene([("b", 2, "2 1 0 0 0", bor_sphere(0.1, 60))]), 3.0),
    "bor_ibc_sphere": (scene([("b", 2, "2 1 10 0 0", bor_sphere(0.1, 60))], ibc="10 constant 100 -150 0 0"), 2.0),
    "bor_dielectric_sphere": (scene([("b", 3, "3 1 0 1 0", bor_sphere(0.1, 60))], diel=D1), 1.5),
    "bor_coated_sphere": (scene([("o", 3, "3 1 0 1 0", bor_sphere(0.1, 60)), ("c", 4, "4 1 0 1 0", bor_sphere(0.07, 60))], diel="1 3.0 -0.06 1.0 0.0"), 1.5),
    "bor_sheet_sphere": (scene([("b", 1, "1 1 10 0 0", bor_sphere(0.1, 60))], ibc="10 constant 200 100 0 0"), 2.0),
    "bor_cone_cylinder": (scene([("b", 2, "2 0 0 0 0", rows([(0, 0.3), (0.1, 0.1), (0.1, -0.1), (0, -0.1)]))]), 3.0),
}
results = {}
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    for name, (g, f) in TWOD.items():
        for method, options in (("dense", dict(factorization="dense")), ("compressed", dict(factorization="compressed"))):
            r = S.solve_monostatic_rcs_2d(g, [f], ANG, geometry_units="meters", execution_options=dict(options, blas_threads=1))
            results["{}/{}".format(name, method)] = np.array([complex(s["rcs_amp_real"], s["rcs_amp_imag"]) for s in r["samples"]])
            print(name, method, flush=True)
    r = S.solve_bistatic_rcs_2d(TWOD["dielectric_circle"][0], [2.0], [0.0, 60.0], [0.0, 45.0, 180.0], geometry_units="meters")
    results["bistatic_dielectric"] = np.array([complex(s["rcs_amp_real"], s["rcs_amp_imag"]) for s in r["samples"]])
    for name, (g, f) in BOR.items():
        r = D.solve_monostatic_rcs_bor(g, [f], [0.0, 30.0, 90.0, 150.0, 180.0], geometry_units="meters", workers=2)
        results[name] = np.array([s["rcs_linear"] for s in r["samples"]])
        print(name, flush=True)
np.savez(out, **results)
print("saved", out, len(results))
