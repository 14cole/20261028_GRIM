"""One strategy for solving many incidence angles with the FMM prototype, in a fresh process.

usage: python angle_study.py '<json spec>'
spec: kind, ka, ppw, angles (count over 0..180 deg), strategy, batch, workers, tol, out
strategies: batch (sequential chunks of `batch` columns), threads, processes, compressed (RHS rank), warm (projection start)
"""
import json, math, os, resource, sys, time
import numpy as np
spec = json.loads(sys.argv[1])
from scatter import Scatterer, gmres_batch
tol = spec.get('tol', 1e-8); m = spec.get('angles', 181); angles = np.linspace(0., 180., m)
t0 = time.perf_counter()
sc = Scatterer(spec['kind'], spec['ka'], points_per_wavelength=spec.get('ppw', 12), digits=spec.get('digits', 8))
setup = time.perf_counter() - t0
B = sc.rhs(angles)
strategy = spec['strategy']; batch = spec.get('batch', 32); workers = spec.get('workers', 1)
chunks = [np.arange(i, min(i + batch, m)) for i in range(0, m, batch)]
X = np.zeros((sc.n, m), complex); its = np.zeros(m, int); info = {}
t1 = time.perf_counter(); c1 = time.process_time()
def solve_chunk(cols):
    x, it, res = gmres_batch(sc.matvec, B[:, cols], tol=tol)
    return cols, x, it
if strategy == 'batch':
    for cols in chunks:
        _, X[:, cols], its[cols] = solve_chunk(cols)
elif strategy == 'threads':
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(workers) as pool:
        for cols, x, it in pool.map(solve_chunk, chunks):
            X[:, cols] = x; its[cols] = it
elif strategy == 'processes':
    import multiprocessing as mp
    with mp.get_context('fork').Pool(workers) as pool:       # the plan is shared copy-on-write
        for cols, x, it in pool.imap_unordered(solve_chunk, chunks):
            X[:, cols] = x; its[cols] = it
elif strategy == 'compressed':
    # the incident fields over angle span a low-dimensional space when angles are densely sampled
    U, s, Vh = np.linalg.svd(B, full_matrices=False)
    rank = int(np.sum(s > spec.get('rank_tol', 1e-9) * s[0])); info['rhs_rank'] = rank
    info['rank_at'] = {t: int(np.sum(s > float(t) * s[0])) for t in ('1e-4', '1e-6', '1e-9', '1e-12')}
    if spec.get('rank_only'):
        print(json.dumps(dict(spec, n=sc.n, perimeter_wavelengths=round(sc.perimeter_wavelengths, 1), **info))); sys.exit(0)
    Y = np.zeros((sc.n, rank), complex); it_basis = np.zeros(rank, int)
    for i in range(0, rank, batch):
        cols = np.arange(i, min(i + batch, rank))
        y, it, _ = gmres_batch(sc.matvec, U[:, cols] * s[cols], tol=tol)
        Y[:, cols] = y; it_basis[cols] = it
    X = Y @ Vh[:rank]; its = np.full(m, 0); info['basis_iterations'] = int(it_basis.sum())
elif strategy == 'warm':
    AX = None; XS = None
    for cols in chunks:
        x0 = None
        if XS is not None:
            Qm, Rm = np.linalg.qr(AX)                       # least-squares start in span of earlier solutions
            x0 = XS @ np.linalg.solve(Rm, Qm.conj().T @ B[:, cols])
        x, it, res = gmres_batch(sc.matvec, B[:, cols], tol=tol, x0=x0)
        X[:, cols] = x; its[cols] = it
        XS = x if XS is None else np.hstack([XS, x]); AX = sc.matvec(XS) if AX is None else np.hstack([AX, sc.matvec(x)])
else:
    raise ValueError(strategy)
wall = time.perf_counter() - t1; cpu = time.process_time() - c1
# residual check on a few columns with fresh products
check = np.linspace(0, m - 1, min(m, 7)).astype(int)
resid = np.linalg.norm(sc.matvec(X[:, check]) - B[:, check], axis=0) / np.linalg.norm(B[:, check], axis=0)
sigma = sc.backscatter(X, angles)
out = dict(spec, n=sc.n, perimeter_wavelengths=round(sc.perimeter_wavelengths, 1), setup_s=round(setup, 2), solve_s=round(wall, 2), cpu_s=round(cpu, 2),
           plan_mib=round(sc.fmm.bytes / 2 ** 20, 1), peak_gib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20, 3),
           iterations_mean=float(its.mean()), iterations_max=int(its.max()), max_checked_residual=float(resid.max()),
           levels=sc.fmm.levels, blas=os.environ.get('OPENBLAS_NUM_THREADS', 'default'), **info)
if spec.get('out'): np.save(spec['out'], sigma)
print(json.dumps(out))
