import sys; sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
import numpy as np, time, scipy.linalg as sl
from ghost_backend.execution.thread_control import threadpool_limits, threadpool_info
print([ (p.get('internal_api'),p.get('num_threads'),p.get('user_api'),p.get('filepath','')[-40:]) for p in threadpool_info()])
rng=np.random.default_rng(0)
for n in (122,234,864,2000):
    A=rng.standard_normal((n,n))+1j*rng.standard_normal((n,n)); B=rng.standard_normal((n,38))+0j
    for nt in (1,2,4):
        with threadpool_limits(limits=nt,user_api='blas'):
            ts=[]
            for _ in range(5):
                t=time.perf_counter(); lu=sl.lu_factor(A); x=sl.lu_solve(lu,B); r=A@x-B; ts.append(time.perf_counter()-t)
        print(n,nt,'min %.4f med %.4f max %.4f'%(min(ts),sorted(ts)[2],max(ts)),flush=True)
