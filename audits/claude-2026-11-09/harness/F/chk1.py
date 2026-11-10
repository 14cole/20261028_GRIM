"""Cost of live memory checks in a compressed solve with tile worker processes (N=5120)."""
import sys, os, time
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp')
from lib import *
if __name__=='__main__':
    from ghost_backend.twod import solver as S
    from ghost_backend.execution import memory_budget as MB
    from ghost_backend.compressed import worker_pool as WP
    T={}
    def wrap(cls,name,key):
        orig=getattr(cls,name)
        def f(*a,**k):
            c=time.thread_time(); w=time.perf_counter()
            try: return orig(*a,**k)
            finally:
                e=T.setdefault(key,[0,0.,0.]); e[0]+=1; e[1]+=time.thread_time()-c; e[2]+=time.perf_counter()-w
        setattr(cls,name,f)
    wrap(MB.MemoryBudget,'limit','limit()'); wrap(MB.MemoryBudget,'require_reload','require_reload()'); wrap(MB.MemoryBudget,'require_construction','require_construction()')
    orig=WP.WorkerPool._memory_snapshot
    def snap(self,incremental):
        c=time.thread_time(); w=time.perf_counter()
        try: return orig(self,incremental)
        finally:
            e=T.setdefault('worker_snapshot(incremental=%s)'%incremental,[0,0.,0.]); e[0]+=1; e[1]+=time.thread_time()-c; e[2]+=time.perf_counter()-w
    WP.WorkerPool._memory_snapshot=snap
    a=float(sys.argv[1]); f=float(sys.argv[2])
    g=circle_geo(a,256,props='2 0 0 0 0')
    c0=os.times(); t=time.time()
    r=S.solve_monostatic_rcs_2d(g,[f],list(np.linspace(0,180,181)),geometry_units='meters',solver_method='auto',execution_options=dict(factorization='compressed',mesh_strategy='global',assembly_threads='auto',blas_threads=1,compressed_storage_mib=0))
    c1=os.times()
    ma=r['metadata']['memory_accounting']
    print('N',r['metadata'].get('dense_largest_system'),'wall',round(time.time()-t,1),'cpu self',round(c1[0]+c1[1]-c0[0]-c0[1],1),'cpu children',round(c1[2]+c1[3]-c0[2]-c0[3],1),'total_checks',ma['total_checks'],ma['construction_checks'])
    for k,(n,cpu,wall) in sorted(T.items()): print('  %-36s calls %6d  cpu %7.2f s  wall %7.2f s  (%.2f ms cpu/call)'%(k,n,cpu,wall,1e3*cpu/max(n,1)))
