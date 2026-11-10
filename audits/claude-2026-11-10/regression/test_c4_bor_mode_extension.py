"""C-4: the automatic BoR mode-cap extension must converge like an explicit cap."""
import warnings
from common import *
from ghost_backend.bor import dispatch as D

ASPECTS = [0, 10, 30, 60, 90, 120, 150, 170, 180]


def run(g, f, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return D.solve_monostatic_rcs_bor(g, [f], ASPECTS, geometry_units="meters", workers=2, **kw)


def values(r):
    return np.array([s["rcs_linear"] for s in r["samples"]])


# Cone-cylinder with an axis tip: the original failing case (cap 19 extended to 31).
cone = scene([("b", 2, "2 0 0 0 0", rows([(0, 0.3), (0.1, 0.1), (0.1, -0.1), (0, -0.1)]))])
explicit = run(cone, 3.0, n_modes=31, mode_tol=1e-13)
used = explicit["metadata"]["per_frequency"][0]["modes_used"]
try:
    automatic = run(cone, 3.0, mode_tol=1e-13)
    error = None
except Exception as exc:  # noqa: BLE001
    automatic, error = None, exc
check("automatic modes with a tight tolerance complete", error is None, repr(error)[:200])
if automatic is not None:
    record = automatic["metadata"]["per_frequency"][0]
    check("automatic run used the same number of modes", record["modes_used"] == used, (record["modes_used"], used))
    d = np.max(np.abs(values(automatic) / values(explicit) - 1))
    check("extended run equals the explicit-cap run", d < 1e-9, "max relative RCS difference {:.2e}".format(d))
# Default tolerance is unchanged by the fix (no extension involved).
default = run(cone, 3.0)
d = np.max(np.abs(10 * np.log10(values(default) / values(explicit))))
check("default tolerance agrees with the tight run", d < 1e-3, "max |dB| {:.2e}".format(d))
# A sphere through the same tight-tolerance path stays on the Mie value.
from ghost_backend.validation import sphere as SP
sphere = scene([("b", 2, "2 1 0 0 0", bor_sphere(0.1, 60))])
r = run(sphere, 3.0, mode_tol=1e-13)
mie = SP.sigma_pec_sphere(0.1, 3e9)
d = np.max(np.abs(10 * np.log10(values(r) / mie)))
check("PEC sphere with tight tolerance within 0.02 dB of Mie", d < 0.02, "max |dB| {:.4f}".format(d))
finish()
