"""RSS timeline of one dense 2D solve with factor lifetimes and stage marks.

usage: python profile_dense.py <root> '<json spec>'
spec: body (pec|diel|coated|airfoil), n or f, storage (auto|memory|disk), threads, angles, out (npz path, optional)
"""
import gc, json, math, os, sys, threading, time, weakref
import numpy as np, psutil
root, spec = sys.argv[1], json.loads(sys.argv[2])
sys.path.insert(0, os.path.join(root, 'tools/GHOST'))
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
C0 = 299792458.0
def circle(a, n, x0=0.0):
    t = -np.linspace(0, 2*np.pi, n+1); p = [(x0+a*np.cos(v), a*np.sin(v)) for v in t]; p[-1] = p[0]
    return '\n'.join('%.15g %.15g %.15g %.15g' % (*p[i], *p[i+1]) for i in range(n))
kind, n = spec['body'], spec.get('n'); units = 'meters'
if kind == 'airfoil':
    g = build_geometry_snapshot(*parse_geometry(open(os.path.join(root, 'airfoil.geo')).read())); f = spec['f']; units = 'inches'
else:
    f = 0.314/(2*math.pi/n)*C0/(2*math.pi)/1e9
    text = {'pec': 'Title: t\nSegment: b 2\nproperties: 2 1 0 0 0\n%s\nIBCS_Resistances:\nDielectrics:\n' % circle(1., n),
            'diel': 'Title: t\nSegment: b 3\nproperties: 3 1 0 1 0\n%s\nIBCS_Resistances:\nDielectrics:\n1 4.0 -0.2 1.0 0.0\n' % circle(1., n),
            'coated': 'Title: t\nSegment: o 3\nproperties: 3 1 0 1 0\n%s\nSegment: c 4\nproperties: 4 1 0 1 0\n%s\nIBCS_Resistances:\nDielectrics:\n1 3.0 -0.06 1.0 0.0\n' % (circle(1., n*10//17), circle(.7, n*7//17))}[kind]
    g = build_geometry_snapshot(*parse_geometry(text))
from ghost_backend.twod import solver as S
from ghost_backend.linalg import dense as D
me = psutil.Process(); t0 = time.perf_counter(); samples = []; events = []; stop = threading.Event()
def rss(): return me.memory_info().rss/2**30
def mark(name, **kw): events.append(dict(t=round(time.perf_counter()-t0, 3), rss=round(rss(), 3), event=name, **kw))
def sample():
    while not stop.is_set(): samples.append((time.perf_counter()-t0, rss())); stop.wait(0.01)
count = [0]
init0, fd0, solve0 = D.DenseFactor.__init__, D.DenseFactor._factor_double, D.DenseFactor.solve
def init(self, matrix, *a, **k):
    count[0] += 1; self._pid = count[0]
    mark('factor_init_begin', id=self._pid, n=len(matrix), label=k.get('label'), owned=k.get('owned_matrix', False), matrix_gib=round(np.asarray(matrix).nbytes/2**30, 3))
    weakref.finalize(self, mark, 'factor_released', id=self._pid)
    init0(self, matrix, *a, **k); mark('factor_init_end', id=self._pid, storage=self.event.get('residual_storage', 'memory'), variant=self.event.get('factor_variant'))
def fd(self):
    mark('lu_begin', id=self._pid); r = fd0(self); mark('lu_end', id=self._pid); return r
first = set()
def solve(self, *a, **k):
    if self._pid not in first: first.add(self._pid); mark('first_solve_begin', id=self._pid)
    return solve0(self, *a, **k)
D.DenseFactor.__init__, D.DenseFactor._factor_double, D.DenseFactor.solve = init, fd, solve
angles = [float(x) for x in np.linspace(0, 180, spec.get('angles', 181))]
th = spec.get('threads', 'auto')
opts = dict(factorization=spec.get('mode','dense'), assembly_threads=th, blas_threads=th, dense_residual_storage=spec.get('storage', 'auto'))
opts.update(spec.get('options', {}))
base = rss(); threading.Thread(target=sample, daemon=True).start(); mark('solve_begin')
err = None
try: r = S.solve_monostatic_rcs_2d_survey(g, [f], angles, geometry_units=units, execution_options=opts, max_panels=200000)
except Exception as e: r = None; err = type(e).__name__+': '+str(e)[:300]
wall = time.perf_counter()-t0; mark('solve_end'); stop.set()
peak_t, peak = max(samples, key=lambda s: s[1])
before = [e for e in events if e['t'] <= peak_t]
out = dict(spec, f_ghz=round(f, 4), wall=round(wall, 2), base_gib=round(base, 3), peak_gib=round(peak, 3), peak_at=round(peak_t, 2),
           last_event_before_peak=before[-1]['event'] + ':' + str(before[-1].get('id', '')) if before else None, error=err, events=events)
if r is not None:
    m = r['metadata']; blob = json.dumps(m, default=str); out.update(paired='paired_polarization_assembly' in blob, selected=(m.get('backend_selection') or {}).get('selected'), dense_forecast=((m.get('backend_selection') or {}).get('candidates') or {}).get('dense', {}).get('peak_gb'), unknowns=m.get('system_unknowns') or max(e.get('n', 0) for e in events), backend=m.get('linear_backend'),
        stages={k: round(v, 2) for k, v in sorted((m.get('stage_seconds') or {}).items(), key=lambda kv: -kv[1])[:7]})
    field = np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in r['samples']])
    if spec.get('out'): np.savez(spec['out'], field=field, timeline=np.array(samples))
    out['field_head'] = [[c.real, c.imag] for c in field[:4]]
print(json.dumps(out))
