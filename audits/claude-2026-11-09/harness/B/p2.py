import sys, time
from geos import *
from ghost_backend.twod import solver as S
name, method = sys.argv[1], sys.argv[2]
g = make(name, N=int(sys.argv[3]) if len(sys.argv) > 3 else 0)
for rep in range(2):
    t = time.time(); r = S.solve_monostatic_rcs_2d(g, [1.5], [0.0, 35.0], geometry_units='meters', solver_method=method); dt = time.time()-t
    m = r['metadata']
    print('time %.2f'%dt, 'panels', m['panel_count'], {k: round(v, 3) for k, v in m['runtime_profile']['stage_seconds'].items()})
    print(m.get('linear_algebra_execution'))
    for ch in ('VV','HH'):
        print(ch, [ (e.get('unknowns'), e.get('factor_variant'), round(e.get('factor_work_seconds',0),3)) for e in m['channel_metadata'][ch].get('dense_events', [])] , m['channel_metadata'][ch].get('dense_factorization_count'))
import scipy.linalg as sl
A = np.random.rand(220,220)+1j*np.random.rand(220,220)
t=time.time(); sl.lu_factor(A); print('plain lu 220', time.time()-t)
