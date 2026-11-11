"""S-5: fine publication is the default; coarse publication is an explicit, unqualified opt-in.

Includes the counterexample from Codex's implementation review (k = 80,
93 modes, two point pairs sharing one layout): the default must meet the
kernel tolerance at the unprobed points, on the native and the NumPy path.
"""
import os
import warnings
from common import *
from scipy.integrate import quad_vec
from ghost_backend.bor import dispatch as D
from ghost_backend.bor import kernels as K
from ghost_backend.bor import streaming

os.environ.pop("GHOST_BOR_NEAR_PUBLISH", None)
check("coarse publication is off by default", not K._near_publish_coarse())
for value, expected in (("fine", False), ("coarse", True), ("COARSE ", True), ("1", False), ("", False)):
    os.environ["GHOST_BOR_NEAR_PUBLISH"] = value
    check("GHOST_BOR_NEAR_PUBLISH={!r} -> coarse {}".format(value, expected), K._near_publish_coarse() is expected)
os.environ.pop("GHOST_BOR_NEAR_PUBLISH", None)

# --- kernel fixture: unprobed points of an accepted chunk --------------------
bad = (1.1390625, 0.0, 1.1390625, 0.11898510425967053)
good = (1.0140625, 0.0, 1.0140625, 0.1017733529476957)
coordinates = [np.full(32, x) for x in bad]
for array, x in zip(coordinates, good):
    array[::4] = x          # every probed point is the benign pair
k, m = 80.0, 92
rp, zp, rq, zq = bad


def integrand(phi):
    r = np.sqrt((rp - rq) ** 2 + (zp - zq) ** 2 + 4 * rp * rq * np.sin(phi / 2) ** 2)
    return np.exp(-1j * k * r) / (4 * np.pi * r) * np.cos(np.arange(m + 2) * phi)


reference = 2 * quad_vec(integrand, 0, np.pi, epsabs=1e-12, epsrel=1e-12)[0]
native = streaming._NATIVE
for backend in ("native", "fallback"):
    if backend == "native" and native is None:
        check("native kernel available", False, "build bor/native/build_kernel.py")
        continue
    streaming._NATIVE = native if backend == "native" else None
    try:
        result = K.modal_kernels_near(*coordinates, k, m)
    finally:
        streaming._NATIVE = native
    error = float(np.max(np.abs(result[1] - reference)) / np.max(np.abs(reference)))
    check("default published kernel at an unprobed point within tolerance ({})".format(backend),
          error <= 1e-10 < K.NEAR_ANGULAR_RTOL, "{:.1e} (tolerance {:.0e})".format(error, K.NEAR_ANGULAR_RTOL))

# --- end to end: default equals the explicit fine mode bit for bit -----------
ASPECTS = [0.0, 45.0, 90.0, 180.0]


def run(g, f, mode):
    if mode is None:
        os.environ.pop("GHOST_BOR_NEAR_PUBLISH", None)
    else:
        os.environ["GHOST_BOR_NEAR_PUBLISH"] = mode
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = D.solve_monostatic_rcs_bor(g, [f], ASPECTS, geometry_units="meters", workers=2)
    os.environ.pop("GHOST_BOR_NEAR_PUBLISH", None)
    return np.array([s["rcs_linear"] for s in r["samples"]])


cases = {
    "PEC sphere ka 10": (scene([("b", 2, "2 1 0 0 0", bor_sphere(0.1, 120))]), 4.7713),
    "cone-cylinder": (scene([("b", 2, "2 0 0 0 0", rows([(0, 0.3), (0.1, 0.1), (0.1, -0.1), (0, -0.1)]))]), 3.0),
}
for name, (g, f) in cases.items():
    default, fine = run(g, f, None), run(g, f, "fine")
    check(name + ": default equals fine mode bitwise", np.array_equal(default, fine))
from ghost_backend.validation import sphere as SP
default = run(*cases["PEC sphere ka 10"], None)
d = float(np.max(np.abs(10 * np.log10(default / SP.sigma_pec_sphere(0.1, 4.7713e9)))))
check("default PEC sphere within 0.005 dB of Mie", d < 0.005, "{:.4f} dB".format(d))
finish()
