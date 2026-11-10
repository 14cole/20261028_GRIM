"""usage: sweep.py workers(auto|N) a f0 nf [factorization] ; GUI-equivalent fresh sweep with thread/RSS sampling"""
import sys, os, time, json, threading
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp'); os.makedirs(os.environ['TMPDIR'],exist_ok=True)
os.environ.setdefault('GHOST_TIMING_CACHE_DIR', os.path.join(os.getcwd(),'timing'))
from lib import *
import psutil
def tree_sample(me):
    procs=[me]+me.children(recursive=True)
    rss=0; running=0; nthreads=0; per=[]
    for p in procs:
        try:
            rss+=p.memory_info().rss
            r=0
            for tid in os.listdir('/proc/%d/task'%p.pid):
                nthreads+=1
                try:
                    with open('/proc/%d/task/%s/stat'%(p.pid,tid)) as s: st=s.read().rsplit(')',1)[1].split()[0]
                    if st=='R': r+=1
                except OSError: pass
            running+=r; per.append(r)
        except Exception: pass
    return rss,running,nthreads,len(procs)
if __name__=='__main__':
    workers=sys.argv[1]; workers=workers if workers=='auto' else int(workers)
    a=float(sys.argv[2]); f0=float(sys.argv[3]); nf=int(sys.argv[4]); fact=sys.argv[5] if len(sys.argv)>5 else None
    na=int(sys.argv[6]) if len(sys.argv)>6 else 181
    from ghost_backend.twod import solver as S
    from ghost_backend.execution.options import automatic_run, execution_scope
    from ghost_backend.execution.fresh_sweep import run_fresh
    prof=automatic_run('monostatic'); opts=prof['execution_options']
    if fact: opts=dict(opts,factorization=fact)
    if len(sys.argv)>7: opts=dict(opts,mesh_strategy=sys.argv[7])
    g=circle_geo(a,256,props='2 0 0 0 0')
    freqs=[round(f0*(1+0.01*i),4) for i in range(nf)]
    kw=dict(geometry_snapshot=g,frequencies_ghz=freqs,elevations_deg=list(np.linspace(0,180,na)),geometry_units='meters',solver_method=prof['solver_method'],max_panels=100000)
    me=psutil.Process(); stop=threading.Event(); S_=[]
    def samp():
        while not stop.wait(0.02): S_.append((time.time(),)+tree_sample(me))
    th=threading.Thread(target=samp,daemon=True); th.start()
    c0=os.times(); t=time.time()
    with execution_scope(opts, limit_blas=True):
        r=run_fresh(S.solve_monostatic_rcs_2d_survey, kw, opts, 'double', False, frequency_workers=workers)
    wall=time.time()-t; stop.set(); th.join(); c1=os.times()
    cpu=sum(c1[i]-c0[i] for i in range(4))
    m=r['metadata']; run=np.array([s[2] for s in S_]); 
    fm=m.get('frequency_metadata',[])
    print(json.dumps(dict(workers=str(workers),wall=round(wall,2),cpu_s=round(cpu,2),freq_exec=m.get('frequency_execution'),
      peak_tree_rss_gib=round(max(s[1] for s in S_)/2**30,3), runnable_mean=round(float(run.mean()),2), runnable_p95=int(np.percentile(run,95)), runnable_max=int(run.max()),
      max_threads=max(s[3] for s in S_), max_procs=max(s[4] for s in S_),
      unknowns=[x['metadata'].get('dense_largest_system') for x in fm] or m.get('dense_largest_system'),
      methods=sorted({x['metadata'].get('solver_method') for x in fm}) or m.get('solver_method'),
      n_samples=len(r['samples']))))
