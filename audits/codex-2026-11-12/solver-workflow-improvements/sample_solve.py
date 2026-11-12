"""Where a solve spends wall time: stage seconds, CPU/wall, and a stack sampler over all threads.

usage: python sample_solve.py <root> '<json spec>'
spec: body, n|f, mode (dense|compressed|automatic), threads, angles, radius (m, default 1), options
The sampler records, every 5 ms, the innermost Python frame of every thread that is not idle in a
queue/lock wait. A thread inside a native kernel or BLAS call shows the Python function that made the call.
"""
import collections, json, math, os, sys, threading, time, resource, hashlib
from pathlib import Path
import numpy as np, psutil
root, spec = sys.argv[1], json.loads(sys.argv[2])
sys.path.insert(0, os.path.join(root, 'tools/GHOST'))
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
C0 = 299792458.0
a = float(spec.get('radius', 1.0))
def circle(r, n):
    t = -np.linspace(0, 2*np.pi, n+1); p = [(r*np.cos(v), r*np.sin(v)) for v in t]; p[-1] = p[0]
    return '\n'.join('%.15g %.15g %.15g %.15g' % (*p[i], *p[i+1]) for i in range(n))
kind, n = spec['body'], spec.get('n'); units = 'meters'
if kind == 'custom':
    g=build_geometry_snapshot(*parse_geometry(Path(spec['geo']).read_text())); f=spec['f']
elif kind == 'airfoil':
    g = build_geometry_snapshot(*parse_geometry(open(os.path.join(root, 'airfoil.geo')).read())); f = spec['f']; units = 'inches'
else:
    f = 0.314/(2*math.pi*a/n)*C0/(2*math.pi)/1e9
    text = {'pec': 'Title: t\nSegment: b 2\nproperties: 2 1 0 0 0\n%s\nIBCS_Resistances:\nDielectrics:\n' % circle(a, n),
            'diel': 'Title: t\nSegment: b 3\nproperties: 3 1 0 1 0\n%s\nIBCS_Resistances:\nDielectrics:\n1 4.0 -0.2 1.0 0.0\n' % circle(a, n),
            'coated': 'Title: t\nSegment: o 3\nproperties: 3 1 0 1 0\n%s\nSegment: c 4\nproperties: 4 1 0 1 0\n%s\nIBCS_Resistances:\nDielectrics:\n1 3.0 -0.06 1.0 0.0\n' % (circle(a, n*10//17), circle(.7*a, n*7//17))}[kind]
    g = build_geometry_snapshot(*parse_geometry(text))
f=float(spec.get('frequency_ghz',f))
from ghost_backend.twod import solver as S
from research_hooks import install
research=install(spec)
if spec.get('force_tile'):os.environ['GHOST_HMATRIX_MIN_UNKNOWNS']='0'
if spec.get('fallback'):
    from ghost_backend.twod.assembly.native import far, near, table
    far.far_block=lambda *a,**kw:None
    far.tile_library=lambda:None
    far.scatter_library=lambda:None
    near.ENABLED=False
    table.library=lambda:None
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
source_hash=hashlib.sha256()
for source in sorted((Path(root)/'tools/GHOST/ghost_backend').rglob('*.py')):
    source_hash.update(source.relative_to(root).as_posix().encode()+b'\0'+source.read_bytes()+b'\0')
t0 = time.perf_counter(); c0 = time.process_time(); err = None
try:
    from ghost_backend.execution.options import cpu_allocation_scope
    with cpu_allocation_scope(4):
        fn=S.solve_monostatic_rcs_2d_certified if spec.get('certified') else S.solve_monostatic_rcs_2d_survey
        frequencies=[f*v for v in spec.get('frequency_factors',[1.])]
        r = fn(g, frequencies, angles, geometry_units=units, execution_options=opts, max_panels=200000, **({'mesh_reference_ghz':max(frequencies)} if spec.get('fixed_mesh') else {}))
except Exception as e: r = None; err = type(e).__name__+': '+str(e)[:300]
wall = time.perf_counter()-t0; cpu = time.process_time()-c0; stop.set()
out = dict(spec, f_ghz=round(f, 5), wall=round(wall, 2), cpu=round(cpu, 2), cpu_over_wall=round(cpu/wall, 2), peak_gib=round(me.memory_info().rss/2**30, 3), error=err)
if r is not None:
    m = r['metadata']
    out['quality_gate'] = m.get('quality_gate')
    out['metadata'] = m
    out['samples_complete'] = r['samples']
    prof = m.get('runtime_profile') or {}
    stages = m.get('stage_seconds') or prof.get('stage_seconds') or prof.get('stages') or {}
    out.update(backend=m.get('linear_backend'), unknowns=m.get('system_unknowns'), stages={k: round(v, 2) for k, v in sorted(stages.items(), key=lambda kv: -kv[1])[:10]} if isinstance(stages, dict) else str(stages)[:300])
    field = np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in r['samples']])
    if spec.get('out'): np.save(spec['out'], field)
total = sum(leaf.values()) or 1
out['samples'] = total
out['top_leaf'] = [(k, round(100*v/total, 1)) for k, v in leaf.most_common(18)]
out['top_stack'] = [(k, round(100*v/total, 1)) for k, v in bystack.most_common(10)]
n1 = sum(leaf1.values()) or 1
out['single_thread_share'] = round(100*n1/(sum(active_hist.values()) or 1), 1)
out['top_leaf_single'] = [(k, round(100*v/n1, 1)) for k, v in leaf1.most_common(16)]
out['top_stack_single'] = [(k, round(100*v/n1, 1)) for k, v in stack1.most_common(12)]
out['active_threads_hist'] = {str(k): round(100*v/sum(active_hist.values()), 1) for k, v in sorted(active_hist.items())} if active_hist else {}
out['source_sha256']=source_hash.hexdigest()
out['research']=research
out['peak_rss_gib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2
print(json.dumps(out,default=str))
