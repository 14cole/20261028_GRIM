"""Analytic 2-D monostatic scattering by a circular cylinder (written for this audit).

Conventions taken from GHOST's documentation, not from any reference code:
time exp(+jwt); incident plane wave u_inc = exp(+j k khat.r) arriving FROM the
look direction khat = (cos phi, sin phi); outgoing waves H_n^(2).

For u_s -> sqrt(2/(pi k r)) exp(-j(kr - pi/4)) P(phi) the monostatic pattern is

    P(phi) = exp(2j k khat.r0) * sum_n (-1)^n r_n

where r0 is the cylinder centre and r_n the n-th reflection coefficient.
GHOST documents u_s ~ exp(-j(kr-pi/4))/sqrt(8 pi k r) * A with A = j*B and stores
B, so the predicted stored amplitude is  B = -4j P  and sigma_2d = |A|^2/(4k).

TM: u = E_z (Dirichlet on PEC).  TE: u = H_z (Neumann on PEC).
A coating of relative (eps, mu) between core radius a and outer radius b:
passive loss has Im(eps), Im(mu) <= 0 under exp(+jwt).
"""
import numpy as np
from scipy import special as sp

C0 = 299792458.0


def _orders(x):
    n = int(np.ceil(abs(x) + 12.0 * abs(x) ** (1.0 / 3.0) + 12))
    return np.arange(-n, n + 1)


def reflection_coefficients(pol, k, b, a=None, eps=1.0, mu=1.0):
    """r_n for orders n. a None: PEC cylinder of radius b. a == 0: homogeneous cylinder (eps, mu).
    Otherwise a PEC core of radius a coated out to b."""
    n = _orders(k * b)
    x = k * b
    J, Jp = sp.jv(n, x), sp.jvp(n, x)
    H, Hp = sp.hankel2(n, x), sp.h2vp(n, x)
    if a is None:
        return n, (-J / H if pol == "TM" else -Jp / Hp)
    if a == 0:           # homogeneous cylinder: interior J_n(k1 rho), regular at the axis
        k1 = k * np.sqrt(complex(eps) * complex(mu))
        k1 = -k1 if k1.imag > 0 else k1
        F, Fp = sp.jv(n, k1 * b), sp.jvp(n, k1 * b)
        G = (k1 / (complex(mu) if pol == "TM" else complex(eps))) * Fp
        return n, -(J * G - k * Jp * F) / (H * G - k * Hp * F)
    k1 = k * np.sqrt(complex(eps) * complex(mu))
    if k1.imag > 0:
        k1 = -k1                                   # decaying branch for exp(+jwt)
    xa, xb = k1 * a, k1 * b
    if pol == "TM":      # F(a) = 0
        F = sp.jv(n, xb) * sp.yv(n, xa) - sp.yv(n, xb) * sp.jv(n, xa)
        Fp = sp.jvp(n, xb) * sp.yv(n, xa) - sp.yvp(n, xb) * sp.jv(n, xa)
        p = complex(mu)
    else:                # F'(a) = 0
        F = sp.jv(n, xb) * sp.yvp(n, xa) - sp.yv(n, xb) * sp.jvp(n, xa)
        Fp = sp.jvp(n, xb) * sp.yvp(n, xa) - sp.yvp(n, xb) * sp.jvp(n, xa)
        p = complex(eps)
    G = (k1 / p) * Fp
    return n, -(J * G - k * Jp * F) / (H * G - k * Hp * F)


def pattern(pol, f_ghz, phi_deg, b, a=None, eps=1.0, mu=1.0, center=(0.0, 0.0)):
    """Monostatic far-field pattern P(phi)."""
    k = 2 * np.pi * f_ghz * 1e9 / C0
    n, r = reflection_coefficients(pol, k, b, a, eps, mu)
    keep = np.isfinite(r)
    total = np.sum(((-1.0) ** np.abs(n[keep])) * r[keep])
    phi = np.radians(np.asarray(phi_deg, float))
    shift = np.exp(2j * k * (center[0] * np.cos(phi) + center[1] * np.sin(phi)))
    return total * shift


def stored_amplitude(pol, *args, **kw):
    """Predicted GHOST amplitude B = -4j P."""
    return -4j * pattern(pol, *args, **kw)


def series_self_check():
    """Independent checks of the series itself (no solver)."""
    out = {}
    k = 2 * np.pi * 3e9 / C0
    # 1. coating of vacuum == bare PEC of the core radius
    for pol in ("TM", "TE"):
        n, r1 = reflection_coefficients(pol, k, 0.07, a=0.05, eps=1.0, mu=1.0)
        m, r0 = reflection_coefficients(pol, k, 0.05)
        common = min(len(n), len(m)) // 2 - 2
        i, j = len(n) // 2, len(m) // 2
        sl = slice(-common, common + 1)
        out[f"vacuum_coating_equals_core_{pol}"] = float(np.nanmax(np.abs(
            r1[i - common:i + common + 1] - r0[j - common:j + common + 1])))
    # 2. lossless scatterer: |1 + 2 r_n| = 1 (unitarity of each partial wave)
    for pol in ("TM", "TE"):
        _, r = reflection_coefficients(pol, k, 0.07, a=0.05, eps=4.0, mu=1.0)
        out[f"lossless_unitarity_{pol}"] = float(np.nanmax(np.abs(np.abs(1 + 2 * r[np.isfinite(r)]) - 1)))
    # 3. passive loss: |1 + 2 r_n| <= 1
    for pol in ("TM", "TE"):
        _, r = reflection_coefficients(pol, k, 0.07, a=0.05, eps=4.0 - 1.0j, mu=1.5 - 0.5j)
        out[f"lossy_max_partial_wave_modulus_{pol}"] = float(np.nanmax(np.abs(1 + 2 * r[np.isfinite(r)])))
    # 4. high-frequency PEC limit: sigma_2d -> pi*a (geometric optics), sigma = 4|P|^2/k
    kk = 2 * np.pi * 60e9 / C0
    for pol in ("TM", "TE"):
        P = pattern(pol, 60.0, [0.0], 0.05)[0]
        out[f"pec_ka{kk*0.05:.0f}_sigma_over_pi_a_{pol}"] = float(4 * abs(P) ** 2 / kk / (np.pi * 0.05))
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(series_self_check(), indent=1))
