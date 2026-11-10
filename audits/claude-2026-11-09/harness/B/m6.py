import sys, time, os, threading
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from geos import *
from ghost_backend.twod import solver as S
for method in ('direct', 'auto'):
    for nthreads in (2, 4):
        for trial in range(3):
            out = {}; errs = {}
            def work(i):
                try: out[i] = S.solve_monostatic_rcs_2d(make('pec'), [1.5], [0.0, 35.0], geometry_units='meters', solver_method=method)
                except Exception as e: errs[i] = type(e).__name__ + ': ' + str(e)[:400]
            ths = [threading.Thread(target=work, args=(i,)) for i in range(nthreads)]
            [t.start() for t in ths]; [t.join() for t in ths]
            print(method, 'threads', nthreads, 'trial', trial, 'ok', len(out), 'failed', len(errs))
            if errs and trial == 0: print('   ', list(errs.values())[0])
# single-pol + bistatic concurrently
out = {}; errs = {}
def w2(i):
    try: out[i] = S.solve_bistatic_rcs_2d(make('pec'), [1.5], [0.0], [0.0, 35.0], geometry_units='meters')
    except Exception as e: errs[i] = type(e).__name__ + ': ' + str(e)[:200]
ths = [threading.Thread(target=w2, args=(i,)) for i in range(3)]
[t.start() for t in ths]; [t.join() for t in ths]
print('bistatic threads 3 ok', len(out), 'failed', len(errs), list(errs.values())[:1])
