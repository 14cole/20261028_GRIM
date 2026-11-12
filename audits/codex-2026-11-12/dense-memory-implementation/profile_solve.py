"""RSS timeline of one dense 2D solve with factor lifetimes and stage marks.

usage: python profile_dense.py <root> '<json spec>'
spec: body (pec|diel|coated|airfoil), n or f, storage (auto|memory|disk), threads, angles, out (npz path, optional)
"""
import hashlib
import gc, json, math, os, sys, threading, time, weakref, resource, traceback
from pathlib import Path
import numpy as np, psutil
root, spec = sys.argv[1], json.loads(sys.argv[2])
source_digest=hashlib.sha256()
for file in sorted((Path(root)/'tools/GHOST/ghost_backend').rglob('*.py')):
    source_digest.update(file.relative_to(root).as_posix().encode()+b'\0'+file.read_bytes()+b'\0')
source_sha256=source_digest.hexdigest()
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
# Independent diagnostics: retain actual planning/admission evidence and every field.
from ghost_backend.execution import memory_budget as MB
from ghost_backend.twod.assembly import session as AS
from ghost_backend.execution.options import current_options
pair_plans=[]; rejected=[]; gate_peaks={}
plan0=AS.plan_paired_assembly
def plan(*a,**k):
    answer=plan0(*a,**k);pair_plans.append(dict(arguments=a,kwargs=k,paired=answer));return answer
AS.plan_paired_assembly=plan
check0=MB.MemoryBudget._check
def check(self,total,allowed,context,**details):
    gate_peaks[context]=max(gate_peaks.get(context,0),total)
    if total>allowed:
        rejected.append(dict(required=total,allowed=allowed,context=context,last=dict(self.last),
            plan=self.plan,options=current_options(),pending=self.pending_construction_bytes,
            details=details,stack=traceback.format_stack(limit=14)))
    return check0(self,total,allowed,context,**details)
MB.MemoryBudget._check=check
cgroup=[]
def cg():
    try:
        stat=dict(line.split() for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines())
        return dict(current=int(Path('/sys/fs/cgroup/memory.current').read_text()),
                    anon=int(stat['anon']),file=int(stat['file']),shmem=int(stat['shmem']),dirty=int(stat['file_dirty']))
    except (OSError,KeyError):return {}
old_sample=sample
def sample():
    tick=0
    while not stop.is_set():
        samples.append((time.perf_counter()-t0,rss()))
        if tick%5==0:cgroup.append((time.perf_counter()-t0,cg()))
        tick+=1;stop.wait(.01)
angles = [float(x) for x in np.linspace(0, 180, spec.get('angles', 181))]
th = spec.get('threads', 'auto')
opts = dict(factorization=spec.get('mode','dense'), assembly_threads=th, blas_threads=th, dense_residual_storage=spec.get('storage', 'auto'))
opts.update(spec.get('options', {}))
base_cgroup=cg(); base = rss(); sampler=threading.Thread(target=sample, daemon=True); sampler.start(); mark('solve_begin')
err = None
try: r = (S.solve_monostatic_rcs_2d_certified if spec.get('certified') else S.solve_monostatic_rcs_2d_survey)(g, [f], angles, geometry_units=units, execution_options=opts, max_panels=200000)
except Exception as e: r = None; err = type(e).__name__+': '+str(e); failure_trace=traceback.format_exc()
wall = time.perf_counter()-t0; mark('solve_end'); stop.set(); sampler.join()
peak_t, peak = max(samples, key=lambda s: s[1])
before = [e for e in events if e['t'] <= peak_t]
out = dict(spec, backend_source_sha256=source_sha256, f_ghz=round(f, 4), wall=round(wall, 2), base_gib=round(base, 3), peak_gib=round(peak, 3), peak_at=round(peak_t, 2),
           last_event_before_peak=before[-1]['event'] + ':' + str(before[-1].get('id', '')) if before else None, error=err, events=events)
if r is not None:
    m = r['metadata']; blob = json.dumps(m, default=str); out.update(paired='paired_polarization_assembly' in blob, selected=(m.get('backend_selection') or {}).get('selected'), dense_forecast=((m.get('backend_selection') or {}).get('candidates') or {}).get('dense', {}).get('peak_gb'), unknowns=m.get('system_unknowns') or max(e.get('n', 0) for e in events), backend=m.get('linear_backend'),
        stages={k: round(v, 2) for k, v in sorted((m.get('stage_seconds') or {}).items(), key=lambda kv: -kv[1])[:7]})
    field = np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in r['samples']])
    if spec.get('out'): np.savez(spec['out'], field=field, timeline=np.array(samples))
    out['field_head'] = [[c.real, c.imag] for c in field[:4]]
out.update(rss_highwater_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2,
           pair_plans=pair_plans, rejected=rejected, gate_peaks=gate_peaks,
           base_cgroup=base_cgroup,peak_cgroup={k:max(row[1].get(k,0) for row in cgroup) for k in base_cgroup},
           final_rss_gib=rss(),quality_gate=None if r is None else r['metadata'].get('quality_gate'),
           failure_trace=None if err is None else failure_trace)
if r is not None:
    meta=r['metadata']
    out['actual_unknowns']=max([e.get('n',0) for e in events]+[x.get('unknowns',0) for x in (meta.get('backend_selection') or {}).get('meshes',[])])
    out['backend_selection']=meta.get('backend_selection')
    out['fields_count']=len(field)
    if spec.get('out'):Path(spec['out']+'.metadata.json').write_text(json.dumps(meta,default=str))
print(json.dumps(out,default=str))
