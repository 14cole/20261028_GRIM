"""One timed solve in a fresh process.  python case.py <root> <spec json>  -> one JSON line."""
import json, math, os, sys, threading, time
root, spec = sys.argv[1], json.loads(sys.argv[2])
os.environ.update({k: str(v) for k, v in spec.get('env', {}).items()})
sys.path.insert(0, os.path.join(root, 'tools', 'GHOST'))
import numpy as np, psutil
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
def snap(text): return build_geometry_snapshot(*parse_geometry(text))
def circle(r, n, cw=True, x0=0.0):
    th = np.linspace(0, 2*np.pi, n+1) * (-1 if cw else 1)
    p = [(x0 + r*math.cos(t), r*math.sin(t)) for t in th]; p[-1] = p[0]
    return '\n'.join('%.15g %.15g %.15g %.15g' % (*p[i], *p[i+1]) for i in range(n))
kind, n = spec['body'], spec.get('n', 0)
C0 = 299792458.0
units = 'meters'
if kind == 'airfoil':
    g = snap(open(os.path.join(root, 'airfoil.geo')).read()); units = 'inches'; f = spec['f']
else:
    a = 1.0
    # panel length such that |k0| L = kl (20 panels per free-space wavelength at kl=0.314)
    f = spec.get('kl', 0.314) / (2*math.pi*a/n) * C0/(2*math.pi)/1e9
    if kind == 'pec': g = snap('Title: t\nSegment: b 2\nproperties: 2 1 0 0 0\n%s\nIBCS_Resistances:\nDielectrics:\n' % circle(a, n))
    elif kind == 'ibc': g = snap('Title: t\nSegment: b 2\nproperties: 2 1 10 0 0\n%s\nIBCS_Resistances:\n10 constant 75 -20 0 0\nDielectrics:\n' % circle(a, n))
    elif kind == 'diel': g = snap('Title: t\nSegment: b 3\nproperties: 3 1 0 1 0\n%s\nIBCS_Resistances:\nDielectrics:\n1 4.0 -0.2 1.0 0.0\n' % circle(a, n))
    elif kind == 'coated':
        g = snap('Title: t\nSegment: o 3\nproperties: 3 1 0 1 0\n%s\nSegment: c 4\nproperties: 4 1 0 1 0\n%s\nIBCS_Resistances:\nDielectrics:\n1 3.0 -0.06 1.0 0.0\n' % (circle(a, n*10//17), circle(0.7*a, n*7//17)))
    elif kind == 'twobody': g = snap('Title: t\nSegment: b 2\nproperties: 2 1 0 0 0\n%s\nSegment: c 2\nproperties: 2 1 0 0 0\n%s\nIBCS_Resistances:\nDielectrics:\n' % (circle(a, n//2), circle(a, n//2, x0=2.05*a)))
from ghost_backend.twod import solver as S
me = psutil.Process(); peak = [0]; stop = threading.Event()
def sample():
    while not stop.is_set():
        try: total = me.memory_info().rss + sum(c.memory_info().rss for c in me.children(recursive=True))
        except Exception: total = 0
        peak[0] = max(peak[0], total); stop.wait(0.05)
base = me.memory_info().rss
t = threading.Thread(target=sample, daemon=True); t.start()
angles = [float(x) for x in np.linspace(0, 180, spec.get('angles', 181))]
opts = dict(factorization=spec['backend'])
opts.update(spec.get('options', {}))
entry = getattr(S, spec.get('entry', 'solve_monostatic_rcs_2d_survey'))
start = time.perf_counter(); cpu0 = time.process_time(); err = None
try:
    r = entry(g, [f], angles, geometry_units=units, execution_options=opts, **({'max_panels': 200000}))
except Exception as e:
    r = None; err = type(e).__name__ + ': ' + str(e)[:200]
wall = time.perf_counter() - start; stop.set(); t.join()
out = dict(spec, f_ghz=round(f, 4), wall=round(wall, 2), parent_cpu=round(time.process_time()-cpu0, 2), peak_tree_gib=round(peak[0]/2**30, 3), base_gib=round(base/2**30, 3), error=err)
if r is not None:
    m = r['metadata']
    out.update(panels=m.get('panel_count'), linear_backend=m.get('linear_backend'), method=m.get('solver_method'),
               stages={k: round(v, 2) for k, v in sorted(m.get('runtime_profile', {}).get('stage_seconds', {}).items(), key=lambda kv: -kv[1])[:6]},
               unknowns=max([e.get('unknowns', 0) for e in m.get('compressed_factors', []) if isinstance(e, dict)] + [m.get('dense_largest_system') or 0]) or None,
               certified=m.get('mesh_convergence_certified'), vv0=r['samples'][0]['rcs_db'], hh0=r['samples'][1]['rcs_db'],
               amp=[[s['rcs_amp_real'], s['rcs_amp_imag']] for s in r['samples'][:8]])
if r is not None:
    from pathlib import Path
    dest = Path(os.environ['REVIEW_RESULT_PATH'])
    dest.with_suffix('.samples.json').write_text(json.dumps(r['samples']))
    dest.with_suffix('.metadata.json').write_text(json.dumps(r['metadata'], default=str))
print(json.dumps(out))
