import sys, time, os, cProfile, pstats, resource, threading
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from ref import *
from ghost_backend.twod import solver as S
kind, method, n, nang = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
prof = len(sys.argv) > 5 and sys.argv[5] == 'prof'
a = 1.0
if kind == 'pec': g = geo([(2, '2 1 0 0 0', rows(a, n))]); core = ('pec',); radii=[a]; mats=[]
if kind == 'ibc': g = geo([(2, '2 1 7 0 0', rows(a, n))], ibc='7 constant 100 50 0 0'); core = ('ibc', 100+50j); radii=[a]; mats=[]
if kind == 'diel': g = geo([(3, '3 1 0 1 0', rows(a, n))], diel='1 2.5 -0.1 1 0'); core = ('diel', 2.5-0.1j, 1.0); radii=[a]; mats=[]
if kind == 'coat': g = geo([(3, '3 1 0 1 0', rows(a, n//2)), (4, '4 1 0 1 0', rows(0.8*a, n//2))], diel='1 2.5 -0.1 1 0'); core = ('pec',); radii=[a, .8*a]; mats=[(2.5-0.1j, 1.0)]
f = float(sys.argv[6]) if len(sys.argv) > 6 else 1.0
ang = list(np.linspace(0, 180, nang))
def rss(): 
    with open('/proc/self/statm') as fh: return int(fh.read().split()[1])*4096
base = rss(); peak = [base]; stop = threading.Event()
def poll():
    while not stop.wait(0.02): peak[0] = max(peak[0], rss())
th = threading.Thread(target=poll, daemon=True); th.start()
if prof: pr = cProfile.Profile(); pr.enable()
t = time.time(); r = S.solve_monostatic_rcs_2d(g, [f], ang, geometry_units='meters', solver_method=method); dt = time.time()-t
if prof: pr.disable()
stop.set(); m = r['metadata']
ndof = m['channel_metadata']['VV'].get('dense_largest_system', 0)
print(f'{kind} {method} panels={m["panel_count"]} dofs={ndof} nang={nang} time={dt:.1f}s base_rss={base/2**20:.0f}MiB peak_rss={peak[0]/2**20:.0f}MiB delta={(peak[0]-base)/2**20:.0f}MiB  16N^2={16*ndof**2/2**20:.0f}MiB  ratio={(peak[0]-base)/(16*max(ndof,1)**2):.2f}')
print({k: round(v, 2) for k, v in m['runtime_profile']['stage_seconds'].items()})
print('solver_method', m['solver_method'], 'reuses', m.get('assembled_system_reuses'), 'fact', m.get('dense_factorization_count'))
for pol in ('TE', 'TM'):
    b = get(r, pol); br = amp(f*1e9, pol, radii, mats, core, 0.0)[0]
    print(pol, 'rel err', abs(b[0]-br)/abs(br), 'spread over angles', np.ptp(np.abs(b))/abs(br))
if prof:
    st = pstats.Stats(pr); st.sort_stats('cumulative').print_stats(70)
