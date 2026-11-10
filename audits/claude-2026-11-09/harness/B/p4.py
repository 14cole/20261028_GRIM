import sys, time, os, threading, tracemalloc
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from ref import *
from ghost_backend.twod import solver as S
kind, method, n, nang = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
entry = sys.argv[5] if len(sys.argv) > 5 else 'co'
a = 1.0
if kind == 'pec': g = geo([(2, '2 1 0 0 0', rows(a, n))])
if kind == 'ibc': g = geo([(2, '2 1 7 0 0', rows(a, n))], ibc='7 constant 100 50 0 0')
if kind == 'diel': g = geo([(3, '3 1 0 1 0', rows(a, n))], diel='1 2.5 -0.1 1 0')
if kind == 'coat': g = geo([(3, '3 1 0 1 0', rows(a, n//2)), (4, '4 1 0 1 0', rows(0.8*a, n//2))], diel='1 2.5 -0.1 1 0')
ang = list(np.linspace(0, 180, nang))
tracemalloc.start(12)
best = [0, None, 0.0]; stop = threading.Event(); t0 = time.time()
def poll():
    while not stop.wait(0.1):
        cur, _ = tracemalloc.get_traced_memory()
        if cur > best[0]*1.03 and cur > 50e6:
            best[0] = cur; best[1] = tracemalloc.take_snapshot(); best[2] = time.time()-t0
th = threading.Thread(target=poll, daemon=True); th.start()
if entry == 'co':
    r = S.solve_monostatic_rcs_2d(g, [1.0], ang, geometry_units='meters', solver_method=method)
elif entry == 'cert':
    r = S.solve_monostatic_rcs_2d_certified(g, [1.0], ang, geometry_units='meters', solver_method=method)
elif entry == 'bi':
    r = S.solve_bistatic_rcs_2d(g, [1.0], ang[:8], ang, geometry_units='meters')
else:
    r = S.solve_monostatic_rcs_2d_single_polarization(g, [1.0], ang, entry, geometry_units='meters', solver_method=method, compute_condition_number=('cond' in sys.argv))
stop.set(); th.join()
cur, peak = tracemalloc.get_traced_memory()
m = r['metadata']; ndof = m.get('dense_largest_system') or m.get('panel_count')
unit = 16*ndof**2
print(f'{kind} {method} {entry} dofs={ndof} traced_peak={peak/2**20:.0f}MiB = {peak/unit:.2f} x 16N^2 ({unit/2**20:.0f}MiB); snapshot at t={best[2]:.1f}s size {best[0]/2**20:.0f}MiB total {time.time()-t0:.0f}s')
snap = best[1]
for st in snap.statistics('traceback')[:8]:
    if st.size < 0.2*unit: break
    print(f'--- {st.size/2**20:.0f} MiB ({st.size/unit:.2f} x) count={st.count}')
    for fr in st.traceback[-6:]:
        print('    ', fr.filename.replace('/home/user/20261028_GRIM/tools/GHOST/', '').replace('/usr/local/lib/python3.13/site-packages/', ''), fr.lineno)
