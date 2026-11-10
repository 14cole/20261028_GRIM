import sys, os, time
sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
import numpy as np
from ghost_backend.linalg import hierarchical as H
from ghost_backend.execution.thread_control import threadpool_limits
from e5_lib import kernel, circle
n=int(sys.argv[1]); nrhs=int(sys.argv[2])
w=2*np.pi/n; xy=circle(n)
A=kernel(xy,100.,w)+0.5*np.eye(n)
with threadpool_limits(limits=1,user_api='blas'):
    f=H.HierarchicalFactor(A,xy)
rng=np.random.default_rng(0); b=rng.standard_normal((n,nrhs))+1j*rng.standard_normal((n,nrhs))
print('load',os.getloadavg(),'n',n,'nrhs',nrhs,'leaves',f.evidence['leaves'],'max_rank',f.evidence['max_rank'])
for rep in range(2):
  for thr in (1,2,4):
    with threadpool_limits(limits=thr,user_api='blas'):
        t=time.perf_counter(); c=time.process_time()
        for _ in range(5): f._apply(b,0)
        ta=(time.perf_counter()-t)/5; ca=(time.process_time()-c)/5
        t=time.perf_counter(); c=time.process_time()
        for _ in range(5): A@b
        tm=(time.perf_counter()-t)/5; cm=(time.process_time()-c)/5
    print('blas threads',thr,'HODLR apply wall %.4fs cpu %.4fs | dense A@b wall %.4fs cpu %.4fs'%(ta,ca,tm,cm))
