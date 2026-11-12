"""Dense memory forecast against measured process memory, per phase. Observation only.

usage: python forecast_accuracy.py <root> '<json spec>'
spec: body (pec|ibc|diel|coated|twobody|airfoil), n or f, storage, threads, options, angles
Records every plan returned by dense_memory.forecast (not altered), a 10 ms RSS
timeline, and factor events; reports the last admitted plan of each system
against the measured assembly-phase and solve-phase peaks.
"""
import json, math, os, sys, threading, time
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
            'ibc': 'Title: t\nSegment: b 2\nproperties: 2 1 10 0 0\n%s\nIBCS_Resistances:\n10 constant 75 -20 0 0\nDielectrics:\n' % circle(1., n),
            'diel': 'Title: t\nSegment: b 3\nproperties: 3 1 0 1 0\n%s\nIBCS_Resistances:\nDielectrics:\n1 4.0 -0.2 1.0 0.0\n' % circle(1., n),
            'coated': 'Title: t\nSegment: o 3\nproperties: 3 1 0 1 0\n%s\nSegment: c 4\nproperties: 4 1 0 1 0\n%s\nIBCS_Resistances:\nDielectrics:\n1 3.0 -0.06 1.0 0.0\n' % (circle(1., n*10//17), circle(.7, n*7//17)),
            'twobody': 'Title: t\nSegment: b 2\nproperties: 2 1 0 0 0\n%s\nSegment: c 2\nproperties: 2 1 0 0 0\n%s\nIBCS_Resistances:\nDielectrics:\n' % (circle(1., n//2), circle(1., n//2, x0=2.05))}[kind]
    g = build_geometry_snapshot(*parse_geometry(text))
from ghost_backend.twod import solver as S
from ghost_backend.linalg import dense as D
from ghost_backend.execution import dense_memory as DM
me = psutil.Process(); t0 = time.perf_counter(); samples = []; events = []; plans = []; stop = threading.Event()
def rss(): return me.memory_info().rss
def now(): return time.perf_counter()-t0
def sample():
    while not stop.is_set(): samples.append((now(), rss())); stop.wait(0.01)
forecast0, pair0 = DM.forecast, DM.pair
def forecast(*a, **k):
    plan = forecast0(*a, **k); plans.append((now(), plan)); return plan
DM.forecast = forecast
init0, fd0 = D.DenseFactor.__init__, D.DenseFactor._factor_double
count = [0]
def init(self, matrix, *a, **k):
    count[0] += 1; self._pid = count[0]; events.append(dict(t=now(), event='factor_begin', id=self._pid, n=len(matrix)))
    init0(self, matrix, *a, **k); events.append(dict(t=now(), event='factor_end', id=self._pid, storage=self.event.get('residual_storage', 'memory')))
D.DenseFactor.__init__ = init
angles = [float(x) for x in np.linspace(0, 180, spec.get('angles', 181))]
th = spec.get('threads', 'auto')
opts = dict(factorization='dense', assembly_threads=th, blas_threads=th, dense_residual_storage=spec.get('storage', 'auto'))
opts.update(spec.get('options', {}))
base = rss(); threading.Thread(target=sample, daemon=True).start(); err = None
try: r = S.solve_monostatic_rcs_2d_survey(g, [f], angles, geometry_units=units, execution_options=opts, max_panels=200000)
except Exception as e: r = None; err = type(e).__name__+': '+str(e)[:300]
wall = now(); stop.set()
G = 2**30
out = dict(spec, wall=round(wall, 2), base_gib=round(base/G, 3), error=err, systems=[])
begins = [e for e in events if e['event'] == 'factor_begin']
ends = [e for e in events if e['event'] == 'factor_end']
bounds = [0.] + [e['t'] for e in ends]
for i, b in enumerate(begins):
    lo, hi = bounds[i], b['t']                       # assembly of system i
    end = ends[i]['t'] if i < len(ends) else wall
    nxt = begins[i+1]['t'] if i+1 < len(begins) else wall
    asm = max([s[1] for s in samples if lo <= s[0] <= hi] or [0])
    fac = max([s[1] for s in samples if hi <= s[0] <= end] or [0])
    sol = max([s[1] for s in samples if end <= s[0] <= nxt] or [0])
    plan = [p for t, p in plans if t <= b['t'] and p['system_dofs'] == b['n']]
    plan = plan[-1] if plan else None
    row = dict(system=i+1, unknowns=b['n'], matrix_gib=round(16*b['n']**2/G, 3), storage=ends[i].get('storage') if i < len(ends) else None,
               measured_gib=dict(assembly=round(asm/G, 3), factorization=round(fac/G, 3), solve=round(sol/G, 3)))
    if plan:
        row.update(forecast_gib={k: round(v/G, 3) for k, v in plan['phase_bytes'].items()}, forecast_peak_gib=round(plan['peak_bytes']/G, 3),
                   planned_storage=plan['residual_storage'], paired=plan['paired_assembly'], partner_gib=round(plan['partner_matrix_bytes']/G, 3),
                   batch=plan['angle_batch_size'], tile=plan['assembly_tile'], capacity_gib=None if plan['capacity_bytes'] is None else round(plan['capacity_bytes']/G, 2))
    out['systems'].append(row)
out['peak_gib'] = round(max(s[1] for s in samples)/G, 3) if samples else None
if r is not None: out['formulation'] = (r['metadata'].get('formulation') or r['metadata'].get('solver_formulation'))
print(json.dumps(out))
