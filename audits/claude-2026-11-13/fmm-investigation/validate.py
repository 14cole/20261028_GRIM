"""Validation of the research FMM prototype: products against direct sums, RCS against the exact
circle series, and the matrix-free solve against a dense solve of the same discrete system."""
import numpy as np, time
from fmm2d import HelmholtzFMM, direct
from scatter import Scatterer, gmres_batch, circle_series, curve
rng = np.random.default_rng(0)
for n, k in ((4000, 60), (16000, 250), (64000, 1000)):
    x, nrm, _ = curve('star', n); a = rng.standard_normal(n) + 1j*rng.standard_normal(n); d = rng.standard_normal(n) + 1j*rng.standard_normal(n)
    rows = rng.choice(n, 64, replace=False); ref = direct(x, nrm, k, a, d, rows)
    t = time.perf_counter(); F = HelmholtzFMM(x, nrm, k, digits=8, leaf_wavelengths=1.5); ts = time.perf_counter() - t
    t = time.perf_counter(); u = F.apply(a, d); ta = time.perf_counter() - t
    print('product: n %6d k %5d setup %.2fs apply %.3fs plan %4.0f MiB error %.1e' % (n, k, ts, ta, F.bytes/2**20, abs(u[rows]-ref).max()/abs(ref).max()))
for ka in (20, 80, 320):
    for ppw in (10, 20, 40):
        sc = Scatterer('circle', ka, points_per_wavelength=ppw); ang = [0., 37., 90.]
        X, its, res = gmres_batch(sc.matvec, sc.rhs(ang), tol=1e-10); ex = circle_series(ka, 1.0)
        print('circle ka %4d ppw %2d n %5d iterations %s RCS relative error %.2e' % (ka, ppw, sc.n, its.tolist(), abs(sc.backscatter(X, ang)-ex).max()/ex))
for kind in ('star', 'cavity'):
    sc = Scatterer(kind, 40, points_per_wavelength=12); A = sc.dense(); ang = [0., 45., 123.]; B = sc.rhs(ang)
    X, its, res = gmres_batch(sc.matvec, B, tol=1e-10); Xd = np.linalg.solve(A, B)
    print('%s n %d solution against dense solve %.1e iterations %s condition %.1f' % (kind, sc.n, abs(X-Xd).max()/abs(Xd).max(), its.tolist(), np.linalg.cond(A)))
