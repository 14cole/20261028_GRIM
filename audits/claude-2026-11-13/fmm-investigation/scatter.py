"""Research prototype: PEC TM scattering by a smooth closed curve, solved with the FMM.

Not part of GHOST and not its discretisation.  Combined-field equation
(1/2 I + D - i eta S) phi = -u_inc, Nystrom with the punctured trapezoid rule and
its diagonal log correction (third order), matrix-free products through fmm2d.HelmholtzFMM, and a
GMRES that advances many right-hand sides (incidence angles) at once.
"""
import math, time
import numpy as np
from scipy.special import hankel1, jv
from scipy import sparse
from fmm2d import HelmholtzFMM

KR6 = np.array([4.967362978287758, -16.20501504859126, 25.85153761832639,
                -22.22599466791883, 9.930104998037539, -1.817995878141594])


def curve(kind, n, a=1.0):
    t = 2 * np.pi * (np.arange(n) + 0.5) / n
    if kind == 'circle':
        r, dr = a * np.ones(n), np.zeros(n)
    elif kind == 'star':
        r, dr = a * (1 + 0.3 * np.cos(5 * t)), -1.5 * a * np.sin(5 * t)
    elif kind == 'cavity':        # deep smooth re-entrant shape (kite-like with a notch)
        r = a * (1 + 0.45 * np.cos(t) + 0.2 * np.cos(2 * t) - 0.25 * np.exp(-((t - np.pi) / 0.35) ** 2))
        dr = a * (-0.45 * np.sin(t) - 0.4 * np.sin(2 * t) + 0.25 * 2 * (t - np.pi) / 0.35 ** 2 * np.exp(-((t - np.pi) / 0.35) ** 2))
    else:
        raise ValueError(kind)
    x = np.stack([r * np.cos(t), r * np.sin(t)], 1)
    tx = np.stack([dr * np.cos(t) - r * np.sin(t), dr * np.sin(t) + r * np.cos(t)], 1)
    speed = np.hypot(tx[:, 0], tx[:, 1])
    normal = np.stack([tx[:, 1], -tx[:, 0]], 1) / speed[:, None]      # outward
    return x, normal, speed * 2 * np.pi / n


class Scatterer:
    def __init__(self, kind, k, points_per_wavelength=12, a=1.0, digits=8, leaf_wavelengths=1.5, n=None):
        self.k = k = float(k); self.eta = k
        if n is None:
            _, _, w0 = curve(kind, 4096, a)
            n = int(math.ceil(w0.sum() / (2 * math.pi / k) * points_per_wavelength / 2) * 2)
        self.x, self.nrm, self.w = curve(kind, n, a)
        self.n = n; self.perimeter_wavelengths = self.w.sum() * k / (2 * math.pi)
        t = time.perf_counter()
        self.fmm = HelmholtzFMM(self.x, self.nrm, k, digits=digits, leaf_wavelengths=leaf_wavelengths)
        # Diagonal (self) terms of the punctured trapezoid rule for the log-singular
        # kernels: int g(t) log|t| dt = h sum' g log|t_j| + h g(0) log(h/2pi) + O(h^3).
        t = 2 * np.pi * (np.arange(n) + 0.5) / n
        def ddt(f):
            F = np.fft.fft(f); m = np.fft.fftfreq(n, 1.0 / n); return np.real(np.fft.ifft(1j * m * F))
        xt, yt = ddt(self.x[:, 0]), ddt(self.x[:, 1]); xtt, ytt = ddt(xt), ddt(yt)
        speed = np.hypot(xt, yt); kappa = (xt * ytt - yt * xtt) / speed ** 3
        single = self.w * (0.25j - (np.euler_gamma + np.log(k * self.w / (4 * np.pi))) / (2 * np.pi))
        double = -self.w * kappa / (4 * np.pi)
        self.correction = sparse.diags(double - 1j * self.eta * single)
        self.setup_seconds = time.perf_counter() - t
        self.products = 0; self.product_columns = 0

    def matvec(self, phi):
        self.products += 1; self.product_columns += 1 if phi.ndim == 1 else phi.shape[1]
        wphi = phi * (self.w if phi.ndim == 1 else self.w[:, None])
        return 0.5 * phi + self.fmm.apply(mono=-1j * self.eta * wphi, dip=wphi) + self.correction @ phi

    def dense(self):
        """Same discrete operator as a matrix (small n only), for validation."""
        n = self.n; d = self.x[:, None, :] - self.x[None, :, :]; r = np.hypot(d[..., 0], d[..., 1]); np.fill_diagonal(r, 1.0)
        kern = 0.25j * (self.k * hankel1(1, self.k * r) * np.einsum('ijk,jk->ij', d, self.nrm) / r - 1j * self.eta * hankel1(0, self.k * r))
        np.fill_diagonal(kern, 0.0)
        return 0.5 * np.eye(n) + kern * self.w[None, :] + self.correction.toarray()

    def rhs(self, angles_deg):
        th = np.deg2rad(np.asarray(angles_deg, float)); dvec = np.stack([np.cos(th), np.sin(th)], 1)
        return -np.exp(1j * self.k * (self.x @ dvec.T))

    def backscatter(self, phi, angles_deg):
        """Monostatic echo width (m) per angle; phi columns match the angles."""
        th = np.deg2rad(np.asarray(angles_deg, float)); xhat = -np.stack([np.cos(th), np.sin(th)], 1)
        pattern = (-1j * self.k * (self.nrm @ xhat.T) - 1j * self.eta) * np.exp(-1j * self.k * (self.x @ xhat.T))
        F = np.einsum('na,na->a', pattern * self.w[:, None], phi)
        return np.abs(F) ** 2 / (4 * self.k)


def circle_series(k, a):
    """Exact monostatic echo width of a PEC circle, TM."""
    nmax = int(k * a + 12 * (k * a) ** (1 / 3) + 20); ns = np.arange(-nmax, nmax + 1)
    s = np.sum((-1.0) ** ns * jv(ns, k * a) / hankel1(ns, k * a))
    return 4 / k * abs(s) ** 2


def gmres_batch(matvec, B, tol=1e-8, maxit=400, x0=None):
    """Unrestarted GMRES for every column of B at once (independent Krylov spaces, shared products).

    Returns X, iterations per column, final relative residuals.  Columns that
    have converged are dropped from later products.
    """
    n, m = B.shape
    X = np.zeros((n, m), complex) if x0 is None else x0.astype(complex).copy()
    R = B - matvec(X) if x0 is not None else B.copy()
    bnorm = np.linalg.norm(B, axis=0); bnorm[bnorm == 0] = 1.0
    beta = np.linalg.norm(R, axis=0)
    its = np.zeros(m, int); res = beta / bnorm
    active = np.where(res > tol)[0]
    if not len(active):
        return X, its, res
    V = [R[:, active] / beta[active]]                 # list of (n, m_active)
    H = np.zeros((maxit + 1, maxit, len(active)), complex)
    g = np.zeros((maxit + 1, len(active)), complex); g[0] = beta[active]
    cs = np.zeros((maxit, len(active)), complex); sn = np.zeros((maxit, len(active)), complex)
    cols = active.copy()                               # original column of each active slot
    alive = np.ones(len(active), bool)
    final_j = np.zeros(len(active), int)
    for j in range(maxit):
        live = np.where(alive)[0]
        W = np.zeros((n, len(active)), complex)
        W[:, live] = matvec(V[j][:, live])
        for i in range(j + 1):
            h = np.einsum('nc,nc->c', V[i].conj(), W); H[i, j] = h; W -= V[i] * h
        hn = np.linalg.norm(W, axis=0); H[j + 1, j] = hn
        V.append(W / np.where(hn == 0, 1.0, hn))
        for i in range(j):                             # apply previous rotations
            t = cs[i].conj() * H[i, j] + sn[i].conj() * H[i + 1, j]
            H[i + 1, j] = -sn[i] * H[i, j] + cs[i] * H[i + 1, j]; H[i, j] = t
        denom = np.sqrt(abs(H[j, j]) ** 2 + abs(H[j + 1, j]) ** 2); denom[denom == 0] = 1.0
        cs[j] = H[j, j] / denom; sn[j] = H[j + 1, j] / denom
        H[j, j] = cs[j].conj() * H[j, j] + sn[j].conj() * H[j + 1, j]; H[j + 1, j] = 0
        g[j + 1] = -sn[j] * g[j]; g[j] = cs[j].conj() * g[j]
        r = abs(g[j + 1]) / bnorm[cols]
        newly = alive & (r <= tol)
        final_j[alive] = j + 1
        alive &= ~newly
        res[cols] = np.where(alive | newly, r, res[cols])
        if not alive.any():
            break
    for c in range(len(active)):
        jj = final_j[c]
        y = np.linalg.solve(np.triu(H[:jj, :jj, c]), g[:jj, c])
        X[:, cols[c]] += sum(V[i][:, c] * y[i] for i in range(jj))
        its[cols[c]] = jj
    return X, its, res
