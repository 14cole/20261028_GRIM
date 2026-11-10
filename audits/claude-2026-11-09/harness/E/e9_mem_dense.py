import sys, os, time, threading, gc
sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
import numpy as np, psutil
from ghost_backend.linalg.dense import DenseFactor
from ghost_backend.execution.options import execution_scope, DEFAULTS
from e5_lib import circle
import scipy.special as sp
mode=sys.argv[1]; n=int(sys.argv[2]); cond=len(sys.argv)>3 and sys.argv[3]=='cond'
proc=psutil.Process()
def build(n):
    xy=circle(n); w=2*np.pi/n
    A=np.empty((n,n),complex,order='F')
    for s in range(0,n,500):
        d=np.linalg.norm(xy[:,None,:]-xy[None,s:s+500,:],axis=2); d[d<1e-14]=w/4
        A[:,s:s+500]=0.25j*sp.hankel1(0,100.*d)*w
    A[np.arange(n),np.arange(n)]+=0.5
    return A,xy
A,xy=build(n); gc.collect()
N2=16*n*n
base=proc.memory_info().rss
peak=[base]; stop=threading.Event()
def samp():
    while not stop.wait(0.003): peak[0]=max(peak[0],proc.memory_info().rss)
th=threading.Thread(target=samp,daemon=True); th.start()
opts=dict(DEFAULTS,blas_threads=1)
if mode=='lu': os.environ['GHOST_HIERARCHICAL_MIN_UNKNOWNS']='0'; opts['dense_residual_storage']='memory'
if mode=='lu_disk': os.environ['GHOST_HIERARCHICAL_MIN_UNKNOWNS']='0'; opts['dense_residual_storage']='disk'
if mode=='hodlr': os.environ['GHOST_HIERARCHICAL_MIN_UNKNOWNS']='1'
rng=np.random.default_rng(0); b=rng.standard_normal((n,64))+1j*rng.standard_normal((n,64))
with execution_scope(opts):
    t=time.perf_counter(); c=time.process_time()
    f=DenseFactor(A,{} if cond else None,'t',owned_matrix=True,coordinates=xy)
    tf=time.perf_counter()-t; cf=time.process_time()-c; pf=peak[0]
    t=time.perf_counter(); c=time.process_time()
    x=f.solve(b)
    ts=time.perf_counter()-t; cs=time.process_time()-c
    time.sleep(0.05)
    after=proc.memory_info().rss
    ev=f.event
    f.restore_original(); f.close()
stop.set()
print('%-8s n=%d N2=%.0fMB base(A resident)=%.0fMB | factor: wall %.1fs cpu %.1fs peak extra=%.2f N2 | solve(64): wall %.2fs cpu %.2fs peak extra=%.2f N2 | retained after=%.2f N2 | variant=%s be=%.1e storage=%s hier=%s'%(
   mode,n,N2/2**20,base/2**20,tf,cf,(pf-base)/N2,ts,cs,(peak[0]-base)/N2,(after-base)/N2,ev.get('factor_variant'),ev['max_backward_error'],ev.get('residual_storage'),
   {k:ev['hierarchical'][k] for k in ('max_rank','factor_bytes','refinements','ordered_copy','builds')} if ev.get('hierarchical') else None))
