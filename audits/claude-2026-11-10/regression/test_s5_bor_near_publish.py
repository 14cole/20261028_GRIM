"""S-5: publishing the coarse near level keeps the fields; the switch restores the former values."""
import os
import warnings
from common import *
from ghost_backend.bor import dispatch as D
from ghost_backend.bor import kernels as K
from ghost_backend.validation import sphere as SP

ASPECTS = [0.0, 45.0, 90.0, 180.0]
worst_probe = [0.0]
original = K._near_check


def recording(kind, fine, coarse):
    error, scale = original(kind, fine, coarse)
    ratio = np.asarray(error) / np.maximum(np.asarray(scale), 1e-280)
    if ratio.size:
        worst_probe[0] = max(worst_probe[0], float(np.nanmax(ratio)))
    return error, scale


K._near_check = recording


def run(g, f, mode):
    os.environ["GHOST_BOR_NEAR_PUBLISH"] = mode
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = D.solve_monostatic_rcs_bor(g, [f], ASPECTS, geometry_units="meters", workers=2)
    return np.array([s["rcs_linear"] for s in r["samples"]])


cases = {
    "PEC sphere ka 10": (scene([("b", 2, "2 1 0 0 0", bor_sphere(0.1, 120))]), 4.7713),
    "coated PEC sphere": (scene([("o", 3, "3 1 0 1 0", bor_sphere(0.1, 60)), ("c", 4, "4 1 0 1 0", bor_sphere(0.07, 60))], diel="1 3.0 -0.06 1.0 0.0"), 1.4314),
    "cone-cylinder": (scene([("b", 2, "2 0 0 0 0", rows([(0, 0.3), (0.1, 0.1), (0.1, -0.1), (0, -0.1)]))]), 3.0),
}
for name, (g, f) in cases.items():
    worst_probe[0] = 0.0
    coarse = run(g, f, "coarse")
    check(name + ": probed coarse/fine discrepancy far inside the 2e-8 tolerance", worst_probe[0] < 1e-9, "{:.1e}".format(worst_probe[0]))
    fine = run(g, f, "fine")
    change = float(np.max(np.abs(coarse / fine - 1)))
    check(name + ": RCS unchanged to 1e-11", change < 1e-11, "{:.1e}".format(change))
    again = run(g, f, "fine")
    check(name + ": fine mode is reproducible bitwise", np.array_equal(fine, again))
os.environ.pop("GHOST_BOR_NEAR_PUBLISH", None)
default = run(*cases["PEC sphere ka 10"], "")
mie = SP.sigma_pec_sphere(0.1, 4.7713e9)
d = float(np.max(np.abs(10 * np.log10(default / mie))))
check("default (coarse) PEC sphere within 0.005 dB of Mie", d < 0.005, "{:.4f} dB".format(d))
finish()
