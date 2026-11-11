from pathlib import Path
p=Path(__file__).parent
s=(p/'claude/profile_dense.py').read_text()
s=s.replace('import gc, json, math, os, sys, threading, time, weakref','import gc, json, math, os, sys, threading, time, weakref, resource, traceback\nfrom pathlib import Path')
s=s.replace('angles = [float(x)', '''# Independent diagnostics: retain actual planning/admission evidence and every field.
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
angles = [float(x)''')
s=s.replace("base = rss(); threading.Thread(target=sample, daemon=True).start(); mark('solve_begin')", "base_cgroup=cg(); base = rss(); sampler=threading.Thread(target=sample, daemon=True); sampler.start(); mark('solve_begin')")
s=s.replace("except Exception as e: r = None; err = type(e).__name__+': '+str(e)[:300]", "except Exception as e: r = None; err = type(e).__name__+': '+str(e); failure_trace=traceback.format_exc()")
s=s.replace("wall = time.perf_counter()-t0; mark('solve_end'); stop.set()", "wall = time.perf_counter()-t0; mark('solve_end'); stop.set(); sampler.join()")
s=s.replace('print(json.dumps(out))', '''out.update(rss_highwater_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2,
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
print(json.dumps(out,default=str))''')
(p/'profile_independent.py').write_text(s)
