import sys, time, os, json
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from ref import *
from ghost_backend.twod import solver as S
n = int(sys.argv[1]); nang = int(sys.argv[2])
g = geo([(2, '2 1 0 0 0', rows(1.0, n))])
for method in ('direct', 'auto'):
    t = time.time(); r = S.solve_monostatic_rcs_2d(g, [1.0], list(np.linspace(0, 180, nang)), geometry_units='meters', solver_method=method); dt = time.time()-t
    m = r['metadata']
    print(method, 'N', n, 'nang', nang, 'time %.1f' % dt, {k: round(v, 2) for k, v in m['runtime_profile']['stage_seconds'].items()})
    if method == 'auto':
        ev = m['compressed_factors'][0]
        print(json.dumps(ev, default=str)[:3000])
        print(m.get('execution_options'))
