"""Analytic baseline: 2-D cylinders (complex amplitude or sigma) and BoR spheres against the series."""
import warnings
from common import *
from ghost_backend.twod import solver as S
from ghost_backend.bor import dispatch as D
from ghost_backend.validation import cylinder as C
from ghost_backend.validation import sphere as SP

A = 0.1
C0 = 299792458.0


def freq(ka):
    return ka * C0 / (2 * math.pi * A) / 1e9


def twod(g, f, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return S.solve_monostatic_rcs_2d(g, [f], [0.0, 37.0], geometry_units="meters", **kw)["samples"]


for backend in ("dense", "compressed"):
    opts = dict(execution_options=dict(factorization=backend))
    for ka in (1.0, 2.405, 5.0):
        f = freq(ka)
        s = twod(scene([("b", 2, "2 1 0 0 0", circle(A, 360))]), f, **opts)
        for pol, name in (("VV", "TE"), ("HH", "TM")):
            exact = C.pec_cylinder_backscatter_amplitude(A, f * 1e9, name)
            err = np.max(np.abs(amp(s, pol) - exact)) / abs(exact)
            check("2D PEC {} ka {} {} complex amplitude".format(backend, ka, pol), err < 2e-5, "{:.1e}".format(err))
        zs = 50 - 200j
        s = twod(scene([("b", 2, "2 1 10 0 0", circle(A, 360))], ibc="10 constant 50 -200 0 0"), f, **opts)
        eps, mu = 4 - 0.2j, 1.0
        sd = twod(scene([("b", 3, "3 1 0 1 0", circle(A, 360))], diel="1 4.0 -0.2 1.0 0.0"), f, **opts)
        sc = twod(scene([("o", 3, "3 1 0 1 0", circle(A, 360)), ("c", 4, "4 1 0 1 0", circle(0.07, 252))], diel="1 3.0 0.0 1.0 0.0"), f, **opts)
        for pol, name in (("VV", "TE"), ("HH", "TM")):
            for label, samples, exact, limit in (
                    ("IBC", s, C.sigma_impedance_cylinder(A, zs, f * 1e9, name), 2e-3),
                    ("dielectric", sd, C.sigma_dielectric_cylinder(A, eps, mu, f * 1e9, name), 2e-3),
                    ("coated PEC", sc, C.sigma_coated_pec_cylinder(0.07, A, 3.0, 1.0, f * 1e9, name), 2e-3)):
                d = np.max(np.abs(db(samples, pol) - 10 * math.log10(exact)))
                check("2D {} {} ka {} {} sigma".format(label, backend, ka, pol), d < limit, "{:.1e} dB".format(d))


def bor(g, f):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = D.solve_monostatic_rcs_bor(g, [f], [0.0, 60.0, 90.0, 180.0], geometry_units="meters", workers=2)
    return np.array([s["rcs_linear"] for s in r["samples"]])


for ka in (1.0, 2.7437, 4.4934):
    f = freq(ka)
    table = (
        ("PEC", scene([("b", 2, "2 1 0 0 0", bor_sphere(A, 60))]), SP.sigma_pec_sphere(A, f * 1e9)),
        ("IBC 100-150j", scene([("b", 2, "2 1 10 0 0", bor_sphere(A, 60))], ibc="10 constant 100 -150 0 0"), SP.sigma_impedance_sphere(A, f * 1e9, 100 - 150j)),
        ("dielectric 4-0.2j", scene([("b", 3, "3 1 0 1 0", bor_sphere(A, 60))], diel="1 4.0 -0.2 1.0 0.0"), SP.sigma_dielectric_sphere(A, 4 - 0.2j, 1.0, f * 1e9)),
        ("coated PEC", scene([("o", 3, "3 1 0 1 0", bor_sphere(A, 60)), ("c", 4, "4 1 0 1 0", bor_sphere(0.07, 60))], diel="1 3.0 -0.06 1.0 0.0"),
         SP.sigma_coated_pec_sphere(0.07, A, 3.0 - 0.06j, 1.0, f * 1e9)),
    )
    for label, g, exact in table:
        d = float(np.max(np.abs(10 * np.log10(bor(g, f) / exact))))
        check("BoR {} sphere ka {} within 0.1 dB of Mie".format(label, ka), d < 0.1, "{:.4f} dB".format(d))
finish()
