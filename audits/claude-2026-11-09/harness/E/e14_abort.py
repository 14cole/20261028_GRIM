import sys, os, time, threading
sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
import numpy as np
from ghost_backend.compressed import hmatrix as HM
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
from ghost_backend.linalg import hierarchical as H
from ghost_backend.execution.options import execution_scope, DEFAULTS
from ghost_backend.execution.thread_control import threadpool_info
from e5_lib import DenseOracle, kernel, circle
n=3000; w=2*np.pi/n; xy=circle(n); r=np.full(n,w)
A=kernel(xy,40.,w)+0.5*np.eye(n)
class Abort(Exception): pass
def raiser(k):
    c=[0]; lock=threading.Lock()
    def cp():
        with lock:
            c[0]+=1
            if c[0]>=k: raise InterruptedError('abort %d'%k)
    return cp,c
base=threading.active_count()
def blas(): return [p['num_threads'] for p in threadpool_info() if p.get('user_api')=='blas']
with execution_scope(dict(DEFAULTS,assembly_threads=4,blas_threads=2),limit_blas=True):
    b0=blas()
    # count checkpoints of a full run
    cp,c=raiser(10**9); op=HM.HMatrixOperator(DenseOracle(A),xy,r,budget=8<<30,checkpoint=cp); total=c[0]
    print('assembly checkpoints',total,'threads',threading.active_count()-base,'blas',blas())
    for k in sorted(set([1,2,5,total//7,total//3,total//2,total-3])):
        cp,c=raiser(k); t=time.time()
        try: HM.HMatrixOperator(DenseOracle(A),xy,r,budget=8<<30,checkpoint=cp); res='NO RAISE'
        except InterruptedError as e: res='raised ok'
        except Exception as e: res='other %s %s'%(type(e).__name__,str(e)[:80])
        time.sleep(0.05)
        print('  abort at',k,'->',res,'in %.2fs'%(time.time()-t),'leftover threads',threading.active_count()-base,'blas',blas())
    cp,c=raiser(10**9); op.checkpoint=cp
    f=HMatrixFactor(op,{},'t',storage_budget_bytes=8<<30,checkpoint=cp); total=c[0]
    print('factor checkpoints',total)
    for k in sorted(set([1,7,total//5,total//2,total-5])):
        cp,c=raiser(k); op.checkpoint=cp; t=time.time()
        try: HMatrixFactor(op,{},'t',storage_budget_bytes=8<<30,checkpoint=cp); res='NO RAISE'
        except InterruptedError as e: res='raised ok'
        except Exception as e: res='other %s %s'%(type(e).__name__,str(e)[:80])
        time.sleep(0.05)
        print('  factor abort at',k,'->',res,'in %.2fs'%(time.time()-t),'leftover threads',threading.active_count()-base,'blas',blas())
    op.checkpoint=lambda:None
    # dense HODLR abort
    for k in (3,40,200):
        cp,c=raiser(k)
        try: H.HierarchicalFactor(A,xy,cp); res='NO RAISE (checkpoints %d)'%c[0]
        except InterruptedError: res='raised ok'
        print('  hodlr abort at',k,'->',res,'leftover threads',threading.active_count()-base,'blas',blas())
    print('blas before',b0,'after',blas())
