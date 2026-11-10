"""usage: run2d.py a_m f_ghz mode [nangles] [mesh] ; prints JSON line with forecast vs measured"""
import sys, os, time, json, threading, resource
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp'); os.makedirs(os.environ['TMPDIR'],exist_ok=True)
os.environ.setdefault('GHOST_TIMING_CACHE_DIR', os.path.join(os.getcwd(),'timing'))
from lib import *
import psutil
a=float(sys.argv[1]); f=float(sys.argv[2]); mode=sys.argv[3]; na=int(sys.argv[4]) if len(sys.argv)>4 else 181
mesh=sys.argv[5] if len(sys.argv)>5 else 'global'
from ghost_backend.twod import solver as S
from ghost_backend.execution.options import DEFAULTS
g=circle_geo(a,256,props='2 0 0 0 0')
at=os.environ.get('AT','auto'); bt=os.environ.get('BT','auto')
opts=dict(factorization=mode, mesh_strategy=mesh, assembly_threads=at if at=='auto' else int(at), blas_threads=bt if bt=='auto' else int(bt), compressed_storage_mib=0)
peak=[0]; stop=threading.Event(); me=psutil.Process()
def samp():
    while not stop.wait(0.02):
        try:
            t=me.memory_info().rss+sum(c.memory_info().rss for c in me.children(recursive=True))
            peak[0]=max(peak[0],t)
        except Exception: pass
base=me.memory_info().rss
th=threading.Thread(target=samp,daemon=True); th.start()
c0=os.times(); t=time.time()
r=S.solve_monostatic_rcs_2d(g,[f],list(np.linspace(0,180,na)),geometry_units='meters',solver_method='auto',execution_options=opts)
wall=time.time()-t; c1=os.times(); cpu=sum(c1[i]-c0[i] for i in range(4)); stop.set(); th.join()
m=r['metadata']
est=[e.get('peak_bytes') for e in m.get('experimental_cpu',{}).get('memory_estimates',[])]
sel=m.get('backend_selection') or {}
out=dict(a=a,f=f,mode=mode,final=m.get('execution_options',{}).get('factorization'),method=m.get('solver_method'),
  unknowns=m.get('dense_largest_system'), wall=round(wall,2), cpu_s=round(cpu,2), base_rss_gib=round(base/2**30,3),
  tree_peak_gib=round(peak[0]/2**30,3), self_maxrss_gib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20,3),
  plan_peak_gib=[round(e/2**30,3) for e in est if e],
  sel={k:{kk:round(vv,3) for kk,vv in v.items() if isinstance(vv,(int,float))} for k,v in sel.get('candidates',{}).items()},
  selected=sel.get('selected'), budget=sel.get('admission_budget_gib'),
  checks=m.get('memory_accounting',{}).get('total_checks'), threads=m.get('execution_threads'),
  stages={k:round(v,2) for k,v in sorted(m.get('runtime_profile',{}).get('stage_seconds',{}).items(), key=lambda kv:-kv[1])[:8]},
  degree=m.get('polynomial_degree'), est_keys=[k for k in m if 'mem' in k.lower() or 'estim' in k.lower()])
print(json.dumps(out))
