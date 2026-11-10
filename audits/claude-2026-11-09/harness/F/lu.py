import sys,time,numpy as np, scipy.linalg as sl
sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
from ghost_backend.execution.thread_control import threadpool_limits, threadpool_info
print([(p['internal_api'],p['num_threads'],p.get('threading_layer'),p.get('version')) for p in threadpool_info()])
A=np.random.rand(720,720)+1j*np.random.rand(720,720)
for nt in (1,2,4):
    with threadpool_limits(limits=nt,user_api='blas'):
        t=time.time(); [sl.lu_factor(A) for _ in range(5)]; print(nt,(time.time()-t)/5)
