"""Calibration of publishing the coarse level of the BoR near angular rule.

Each case is solved with GHOST_BOR_NEAR_PUBLISH=fine (former values) and with
the default.  Reported per case: operator time of both, the largest
coarse-against-fine discrepancy seen at any probed point (relative to that
point's largest kernel value; the acceptance tolerance is 2e-8), the number of
probed chunks that fell back, and the largest relative change of the RCS.
"""
import math
import os
import sys
import time
import warnings

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "regression"))
from common import *
from ghost_backend.bor import dispatch as D
from ghost_backend.bor import kernels as K
from ghost_backend.validation import sphere as SP

record = dict(worst=0.0, checks=0)
original_check = K._near_check


def recording_check(kind, fine, coarse):
    error, scale = original_check(kind, fine, coarse)
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.asarray(error) / np.maximum(np.asarray(scale), 1e-280)
    if ratio.size:
        record["worst"] = max(record["worst"], float(np.nanmax(ratio)))
    record["checks"] += 1
    return error, scale


K._near_check = recording_check


def ogive(length, radius, count):
    # circular-arc ogive: generatrix from the nose (0, L/2) to the tail (0, -L/2)
    big = (radius**2 + (length / 2) ** 2) / (2 * radius)
    half = math.asin((length / 2) / big)
    pts = [(big * math.cos(t) - (big - radius), big * math.sin(t)) for t in np.linspace(half, -half, count + 1)]
    pts[0], pts[-1] = (0.0, length / 2), (0.0, -length / 2)
    return rows(pts)


D1 = "1 4.0 -0.2 1.0 0.0"
CASES = [
    ("PEC sphere ka 3", scene([("b", 2, "2 1 0 0 0", bor_sphere(0.1, 60))]), 1.4314, ("pec", 0.1)),
    ("PEC sphere ka 10", scene([("b", 2, "2 1 0 0 0", bor_sphere(0.1, 120))]), 4.7713, ("pec", 0.1)),
    ("PEC sphere ka 30", scene([("b", 2, "2 1 0 0 0", bor_sphere(0.1, 300))]), 14.3139, ("pec", 0.1)),
    ("IBC sphere 100-150j ka 6", scene([("b", 2, "2 1 10 0 0", bor_sphere(0.1, 90))], ibc="10 constant 100 -150 0 0"), 2.8628, None),
    ("sheet sphere 200+100j ka 4", scene([("b", 1, "1 1 10 0 0", bor_sphere(0.1, 60))], ibc="10 constant 200 100 0 0"), 1.9085, None),
    ("dielectric sphere 4-0.2j ka 3", scene([("b", 3, "3 1 0 1 0", bor_sphere(0.1, 60))], diel=D1), 1.4314, ("diel", 0.1)),
    ("lossy dielectric 4-4j ka 3", scene([("b", 3, "3 1 0 1 0", bor_sphere(0.1, 60))], diel="1 4.0 -4.0 1.0 0.0"), 1.4314, None),
    ("coated PEC sphere ka 3", scene([("o", 3, "3 1 0 1 0", bor_sphere(0.1, 60)), ("c", 4, "4 1 0 1 0", bor_sphere(0.07, 60))], diel="1 3.0 -0.06 1.0 0.0"), 1.4314, None),
    ("PEC cone-cylinder 6 GHz", scene([("b", 2, "2 0 0 0 0", rows([(0, 0.3), (0.1, 0.1), (0.1, -0.1), (0, -0.1)]))]), 6.0, None),
    ("PEC ogive 4 GHz", scene([("b", 2, "2 1 0 0 0", ogive(0.5, 0.05, 120))]), 4.0, None),
    ("PEC finite cylinder 5 GHz", scene([("b", 2, "2 0 0 0 0", rows([(0, 0.25), (0.05, 0.25), (0.05, -0.25), (0, -0.25)]))]), 5.0, None),
]
ASPECTS = [0.0, 20.0, 45.0, 90.0, 135.0, 180.0]
print("{:<32} {:>8} {:>8} {:>7} {:>11} {:>9} {:>11} {:>10}".format(
    "case", "fine s", "coarse s", "saved", "probe max", "fallback", "RCS change", "Mie dB"))
for name, g, f, reference in CASES:
    values, times = {}, {}
    for mode in ("fine", "coarse"):
        os.environ["GHOST_BOR_NEAR_PUBLISH"] = mode
        record.update(worst=0.0, checks=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            start = time.perf_counter()
            r = D.solve_monostatic_rcs_bor(g, [f], ASPECTS, geometry_units="meters", workers=2)
        times[mode] = r["metadata"]["runtime_profile"]["stage_seconds"].get("operators", time.perf_counter() - start)
        values[mode] = np.array([s["rcs_linear"] for s in r["samples"]])
        if mode == "coarse":
            probe = record["worst"]
    change = float(np.max(np.abs(values["coarse"] / values["fine"] - 1)))
    mie = ""
    if reference is not None:
        exact = SP.sigma_pec_sphere(reference[1], f * 1e9) if reference[0] == "pec" else SP.sigma_dielectric_sphere(reference[1], 4.0 - 0.2j, 1.0, f * 1e9)
        mie = "{:.4f}".format(float(np.max(np.abs(10 * np.log10(values["coarse"] / exact)))))
    print("{:<32} {:>8.2f} {:>8.2f} {:>6.1f}% {:>11.1e} {:>9} {:>11.1e} {:>10}".format(
        name, times["fine"], times["coarse"], 100 * (1 - times["coarse"] / times["fine"]), probe,
        "no" if probe <= K.NEAR_ANGULAR_RTOL else "YES", change, mie), flush=True)
