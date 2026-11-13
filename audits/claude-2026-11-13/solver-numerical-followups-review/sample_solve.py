"""Where a solve spends wall time: stage seconds, CPU/wall, and a stack sampler over all threads.

usage: python sample_solve.py <root> '<json spec>'
spec: body, n|f, mode (dense|compressed|automatic), threads, angles, radius (m, default 1), options
The sampler records, every 5 ms, the innermost Python frame of every thread that is not idle in a
queue/lock wait. A thread inside a native kernel or BLAS call shows the Python function that made the call.
"""
import collections, json, math, os, sys, threading, time
import numpy as np, psutil
root, spec = sys.argv[1], json.loads(sys.argv[2])
sys.path.insert(0, os.path.join(root, 'tools/GHOST'))
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
C0 = 299792458.0
a = float(spec.get('radius', 1.0))
for _k, _v in (spec.get('env') or {}).items(): os.environ[_k] = str(_v)
def circle(r, n):
    t = -np.linspace(0, 2*np.pi, n+1); p = [(r*np.cos(v), r*np.sin(v)) for v in t]; p[-1] = p[0]
    return '\n'.join('%.15g %.15g %.15g %.15g' % (*p[i], *p[i+1]) for i in range(n))
kind, n = spec['body'], spec.get('n'); units = 'meters'
if kind == 'airfoil':
    g = build_geometry_snapshot(*parse_geometry(open(os.path.join(root, 'airfoil.geo')).read())); f = spec['f']; units = 'inches'
else:
    f = 0.314/(2*math.pi*a/n)*C0/(2*math.pi)/1e9
    text = {'pec': 'Title: t\nSegment: b 2\nproperties: 2 1 0 0 0\n%s\nIBCS_Resistances:\nDielectrics:\n' % circle(a, n),
            'diel': 'Title: t\nSegment: b 3\nproperties: 3 1 0 1 0\n%s\nIBCS_Resistances:\nDielectrics:\n1 4.0 -0.2 1.0 0.0\n' % circle(a, n),
            'coated': 'Title: t\nSegment: o 3\nproperties: 3 1 0 1 0\n%s\nSegment: c 4\nproperties: 4 1 0 1 0\n%s\nIBCS_Resistances:\nDielectrics:\n1 3.0 -0.06 1.0 0.0\n' % (circle(a, n*10//17), circle(.7*a, n*7//17))}[kind]
    g = build_geometry_snapshot(*parse_geometry(text))
from ghost_backend.twod import solver as S
from ghost_backend.linalg import dense as _D
_calls = [0]
_ai = _D.DenseFactor._apply_inverse
def _counted(self, *a, **k):
    _calls[0] += 1
    return _ai(self, *a, **k)
_D.DenseFactor._apply_inverse = _counted
IDLE = {'wait', '_worker', 'get', 'acquire', 'select', 'sample', 'result', '_recv', 'poll', 'join', 'sleep', '_wait_for_tstate_lock'}
leaf1 = collections.Counter(); stack1 = collections.Counter(); leaf = collections.Counter(); bystack = collections.Counter(); active_hist = collections.Counter(); stop = threading.Event()
me = psutil.Process()
def sample():
    own = threading.get_ident()
    while not stop.is_set():
        active = 0; seen = []
        for tid, frame in sys._current_frames().items():
            if tid == own: continue
            code = frame.f_code
            if code.co_name in IDLE: continue
            active += 1
            key = '%s:%s' % (os.path.basename(code.co_filename), code.co_name)
            leaf[key] += 1
            chain = []; fr = frame
            while fr is not None and len(chain) < 4:
                chain.append('%s:%s' % (os.path.basename(fr.f_code.co_filename), fr.f_code.co_name)); fr = fr.f_back
            bystack[' < '.join(chain)] += 1; seen.append((key, ' < '.join(chain)))
        active_hist[active] += 1
        if active == 1: leaf1[seen[0][0]] += 1; stack1[seen[0][1]] += 1
        stop.wait(0.005)
angles = [float(x) for x in np.linspace(0, 180, spec.get('angles', 181))]
th = spec.get('threads', 'auto')
opts = dict(factorization=spec.get('mode', 'dense'), assembly_threads=th, blas_threads=th); opts.update(spec.get('options', {}))
if spec.get('sample', True): threading.Thread(target=sample, daemon=True).start()
t0 = time.perf_counter(); c0 = time.process_time(); err = None
try: r = S.solve_monostatic_rcs_2d_survey(g, [f], angles, geometry_units=units, execution_options=opts, max_panels=200000)
except Exception as e: r = None; err = type(e).__name__+': '+str(e)[:300]
wall = time.perf_counter()-t0; cpu = time.process_time()-c0; stop.set()
out = dict(spec, f_ghz=round(f, 5), wall=round(wall, 2), cpu=round(cpu, 2), cpu_over_wall=round(cpu/wall, 2), peak_gib=round(__import__('resource').getrusage(__import__('resource').RUSAGE_SELF).ru_maxrss/2**20, 3), error=err)
if r is not None:
    m = r['metadata']
    prof = m.get('runtime_profile') or {}
    stages = m.get('stage_seconds') or prof.get('stage_seconds') or prof.get('stages') or {}
    out.update(backend=m.get('linear_backend'), unknowns=m.get('system_unknowns'), stages={k: round(v, 2) for k, v in sorted(stages.items(), key=lambda kv: -kv[1])[:10]} if isinstance(stages, dict) else str(stages)[:300])
    def _find(o, key, acc):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == key and isinstance(v, (int, float)): acc.append(v)
                else: _find(v, key, acc)
        elif isinstance(o, list):
            for v in o: _find(v, key, acc)
        return acc
    out['refinement_steps'] = max(_find(m, 'linear_refinement_steps', []) or [None], key=lambda v: -1 if v is None else v)
    out['condition'] = max(_find(m, 'condition_est', []) or [None], key=lambda v: -1 if v is None else v)
    out['equilibrated_backward_error'] = max(_find(m, 'linear_equilibrated_backward_error', []) or [None], key=lambda v: -1 if v is None else v)
    field = np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in r['samples']])
    if spec.get('out'): np.save(spec['out'], field)
total = sum(leaf.values()) or 1
out['dense_inverse_applications'] = _calls[0]
out['samples'] = total
out['top_leaf'] = [(k, round(100*v/total, 1)) for k, v in leaf.most_common(18)]
out['top_stack'] = [(k, round(100*v/total, 1)) for k, v in bystack.most_common(10)]
n1 = sum(leaf1.values()) or 1
out['single_thread_share'] = round(100*n1/(sum(active_hist.values()) or 1), 1)
out['top_leaf_single'] = [(k, round(100*v/n1, 1)) for k, v in leaf1.most_common(16)]
out['top_stack_single'] = [(k, round(100*v/n1, 1)) for k, v in stack1.most_common(12)]
out['active_threads_hist'] = {str(k): round(100*v/sum(active_hist.values()), 1) for k, v in sorted(active_hist.items())} if active_hist else {}
print(json.dumps(out))
