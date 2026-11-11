"""Concurrent H-matrix and dense solves in one process: no deadlock, same fields, BLAS limits restored."""
import faulthandler, math, sys, threading, time
from pathlib import Path
import numpy as np
root = Path(sys.argv[1]); sys.path.insert(0, str(root/'tools/GHOST'))
faulthandler.dump_traceback_later(900, exit=True)   # a deadlock prints every thread's stack and exits non-zero
from ghost_backend.twod import solver as S
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
from ghost_backend.execution.thread_control import threadpool_info
from ghost_backend.execution.options import execution_scope
def circle(n, kind):
    t = -np.linspace(0, 2*np.pi, n+1); p = [(np.cos(a), np.sin(a)) for a in t]; p[-1] = p[0]
    rows = '\n'.join('%.15g %.15g %.15g %.15g' % (*p[i], *p[i+1]) for i in range(n))
    head = 'Title: c\nSegment: b 2\nproperties: 2 1 0 0 0\n' if kind == 'pec' else 'Title: c\nSegment: b 3\nproperties: 3 1 0 1 0\n'
    tail = '\nIBCS_Resistances:\nDielectrics:\n' + ('' if kind == 'pec' else '1 4.0 -0.2 1.0 0.0\n')
    return build_geometry_snapshot(*parse_geometry(head+rows+tail)), 0.314/(2*math.pi/n)*299792458/(2*math.pi)/1e9
angles = [float(x) for x in np.linspace(0, 180, 91)]
T = dict(assembly_threads=2, blas_threads='auto')
jobs = {
 'hmatrix_pec': ('pec', 2400, dict(T, factorization='automatic', ram_budget_gib=0.45)),
 'dense_pec':   ('pec', 2400, dict(T, factorization='dense')),
 'hmatrix_diel': ('diel', 1200, dict(T, factorization='automatic', ram_budget_gib=0.45)),
 'dense_blas2': ('pec', 2000, dict(assembly_threads=2, blas_threads=2, factorization='dense')),
}
def run(name):
    kind, n, opts = jobs[name]; g, f = circle(n, kind)
    if name == 'hmatrix_diel':
        with execution_scope(opts):
            r = S.solve_monostatic_rcs_2d_survey(g, [f], angles, geometry_units='meters', max_panels=100000)
    else:
        r = S.solve_monostatic_rcs_2d_survey(g, [f], angles, geometry_units='meters', execution_options=opts, max_panels=100000)
    return r['metadata'].get('linear_backend'), np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in r['samples']])
def pools(): return sorted((p.get('internal_api'), p.get('num_threads')) for p in threadpool_info() if p.get('user_api') == 'blas')
before = pools(); ref = {}
for name in jobs:
    t = time.perf_counter(); ref[name] = run(name); print('sequential', name, ref[name][0], '%.1fs' % (time.perf_counter()-t), flush=True)
assert pools() == before, (before, pools())
for name in jobs: assert ref[name][0] == ('cpu_hmatrix' if name.startswith('hmatrix') else 'cpu'), (name, ref[name][0])
ok = True
for round_ in range(3):
    got, errors = {}, {}
    def work(name):
        try: got[name] = run(name)
        except BaseException as e: errors[name] = repr(e)[:300]
    threads = [threading.Thread(target=work, args=(n,)) for n in jobs]
    t = time.perf_counter(); [x.start() for x in threads]; [x.join() for x in threads]
    for name in jobs:
        if name in errors: print('round', round_, name, 'ERROR', errors[name]); ok = False; continue
        d = abs(got[name][1]-ref[name][1]).max()/abs(ref[name][1]).max()
        same = got[name][0] == ref[name][0]
        print('round', round_, name, got[name][0], 'diff %.1e' % d, '' if same else 'BACKEND CHANGED from '+str(ref[name][0])); ok &= same
        ok &= d < 1e-8
    print('round', round_, 'wall %.1fs' % (time.perf_counter()-t), 'pools restored', pools() == before, flush=True)
    ok &= pools() == before
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
