import sys, time, os, json
from ref import *
from ghost_backend.twod import solver as S
n = int(sys.argv[1]); nang = int(sys.argv[2])
g = geo([(2, '2 1 0 0 0', rows(1.0, n))])
ang = list(np.linspace(0, 180, nang))
print('env OPENBLAS_NUM_THREADS =', os.environ.get('OPENBLAS_NUM_THREADS'))
for label, kw in (('auto(default)', dict()),
                  ('auto+dense+global', dict(execution_options=dict(factorization='dense', mesh_strategy='global', assembly_threads='auto', blas_threads='auto'))),
                  ('direct+threads auto', dict(solver_method='direct', execution_options=dict(factorization='dense', assembly_threads='auto', blas_threads='auto'))),
                  ('direct(bare)', dict(solver_method='direct'))):
    try:
        t = time.time(); r = S.solve_monostatic_rcs_2d(g, [1.0], ang, geometry_units='meters', **kw); dt = time.time()-t
    except Exception as e:
        print(label, 'ERROR', type(e).__name__, str(e)[:200]); continue
    m = r['metadata']
    la = m.get('linear_algebra_execution') or []
    print(f'{label:22s} N={n} nang={nang} time={dt:.1f}s method={m["solver_method"]}', {k: round(v, 2) for k, v in m['runtime_profile']['stage_seconds'].items() if v > 0.3},
          'blas:', [(e.get('matrix_size'), e.get('requested_threads')) for e in la][:2], 'opts:', {k: (m.get('execution_options') or {}).get(k) for k in ('factorization', 'assembly_threads', 'blas_threads', 'mesh_strategy')}, flush=True)
