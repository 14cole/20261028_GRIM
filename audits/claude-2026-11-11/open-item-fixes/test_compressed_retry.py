"""Explicit Compressed: a rejected tile inverse is retried with the hierarchical operator.

usage: python test_compressed_retry.py <checkout root>
"""
import math, os, sys, time
from pathlib import Path
import numpy as np
root = Path(sys.argv[1]); sys.path.insert(0, str(root/'tools/GHOST'))
from ghost_backend.twod import solver as S
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
def circle(a, n, x0=0.):
    t = -np.linspace(0, 2*np.pi, n+1); p = [(x0+a*np.cos(v), a*np.sin(v)) for v in t]; p[-1] = p[0]
    return '\n'.join('%.15g %.15g %.15g %.15g' % (*p[i], *p[i+1]) for i in range(n))
def body(kind, n):
    if kind == 'pec': text = 'Title: t\nSegment: b 2\nproperties: 2 1 0 0 0\n%s\nIBCS_Resistances:\nDielectrics:\n' % circle(1., n)
    else: text = 'Title: t\nSegment: o 3\nproperties: 3 1 0 1 0\n%s\nSegment: c 4\nproperties: 4 1 0 1 0\n%s\nIBCS_Resistances:\nDielectrics:\n1 3.0 -0.06 1.0 0.0\n' % (circle(1., n*10//17), circle(.7, n*7//17))
    return build_geometry_snapshot(*parse_geometry(text)), 0.314/(2*math.pi/n)*299792458/(2*math.pi)/1e9
angles = [float(x) for x in np.linspace(0, 180, 181)]
T = dict(assembly_threads='auto', blas_threads='auto')
def solve(kind, n, mode, env=None):
    g, f = body(kind, n); old = dict(os.environ); os.environ.update(env or {})
    t = time.perf_counter()
    try:
        r = S.solve_monostatic_rcs_2d_survey(g, [f], angles, geometry_units='meters', execution_options=dict(T, factorization=mode), max_panels=200000)
        m = r['metadata']
        return dict(backend=m.get('linear_backend'), retry=m.get('compressed_hmatrix_retry'), wall=time.perf_counter()-t,
                    field=np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in r['samples']]))
    except Exception as exc:
        return dict(error=type(exc).__name__, message=str(exc), wall=time.perf_counter()-t)
    finally:
        os.environ.clear(); os.environ.update(old)
checks = []
def check(name, ok, detail=''):
    ok = bool(ok); checks.append(ok); print(('ok   ' if ok else 'FAIL ') + name + (' ' + str(detail) if detail else ''), flush=True)
for kind, n in (('pec', 8000), ('coated', 4080)):
    c = solve(kind, n, 'compressed'); d = solve(kind, n, 'dense')
    check('%s %d: explicit compressed completes' % (kind, n), 'error' not in c, c.get('message', '')[:200] or '%.1fs' % c['wall'])
    if 'error' in c: continue
    check('%s %d: completed with the hierarchical operator' % (kind, n), c['backend'] == 'cpu_hmatrix', c['backend'])
    retry = c['retry'] or {}
    check('%s %d: metadata records the rejected tile attempt' % (kind, n), retry.get('rejected_tile_attempt', {}).get('error') in ('HierarchicalRejected', 'HierarchicalCapacityRejected'),
          {k: (round(v, 1) if isinstance(v, float) else str(v)[:90]) for k, v in retry.get('rejected_tile_attempt', {}).items()})
    diff = abs(c['field']-d['field']).max()/abs(d['field']).max()
    check('%s %d: all %d amplitudes agree with dense' % (kind, n, len(d['field'])), diff < 1e-6, '%.1e (dense %.1fs)' % (diff, d['wall']))
# A launch threshold override is the user's choice: no retry.
c = solve('pec', 8000, 'compressed', env={'GHOST_HMATRIX_MIN_UNKNOWNS': '8192'})
check('threshold override: rejection is not retried', c.get('error') in ('HierarchicalRejected', 'HierarchicalCapacityRejected'), c.get('error') or c.get('backend'))
check('rejection advice mentions Automatic', 'Automatic' in c.get('message', ''), c.get('message', '')[-260:])
# Where the tile inverse is accepted nothing changes.
c = solve('pec', 3000, 'compressed')
check('pec 3000: tile operator still used, no retry recorded', c.get('backend') == 'cpu_compressed' and c.get('retry') is None, c.get('backend'))
print('%d passed, %d failed' % (sum(checks), len(checks)-sum(checks))); sys.exit(0 if all(checks) else 1)
