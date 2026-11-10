import sys, os, time, cProfile, pstats, io
sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
import numpy as np, scipy.linalg as la
from ghost_backend.compressed import hmatrix as HM
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
from ghost_backend.execution.options import execution_scope, DEFAULTS
from e5_lib import DenseOracle, kernel, circle
n=int(sys.argv[1]); thr=int(sys.argv[2]); nrhs=int(sys.argv[3])
w=2*np.pi/n; xy=circle(n); r=np.full(n,w)
A=kernel(xy,float(sys.argv[4]) if len(sys.argv)>4 else 100.,w)+0.5*np.eye(n)
def prof(label,fn):
    pr=cProfile.Profile(); t=time.perf_counter(); c=time.process_time()
    pr.enable(); out=fn(); pr.disable()
    print('### %s wall %.2fs cpu %.2fs'%(label,time.perf_counter()-t,time.process_time()-c))
    s=io.StringIO(); pstats.Stats(pr,stream=s).sort_stats('tottime').print_stats(9); 
    print('\n'.join(l[:150] for l in s.getvalue().splitlines()[4:22]))
    return out
with execution_scope(dict(DEFAULTS,assembly_threads=thr,blas_threads=thr)):
    op=prof('assemble',lambda:HM.HMatrixOperator(DenseOracle(A),xy,r,budget=8<<30))
    print(op.evidence['max_rank'],op.evidence['interaction_lists'],'bytes/dense',op.bytes/(16*n*n))
    rng=np.random.default_rng(5); b=rng.standard_normal((n,nrhs))+1j*rng.standard_normal((n,nrhs))
    f=prof('factor(no cond)',lambda:HMatrixFactor(op,None,'t',storage_budget_bytes=8<<30))
    x=prof('solve %d rhs'%nrhs,lambda:f.solve(b))
    prof('matmul %d rhs x10'%nrhs,lambda:[op.matmul(b) for _ in range(10)])
    prof('matmul 1 rhs x10',lambda:[op.matmul(b[:,0]) for _ in range(10)])
    prof('precond apply x10',lambda:[f.factor.apply(b,solve=True) for _ in range(10)])
    d={}
    prof('factor+cond',lambda:HMatrixFactor(op,d,'t',storage_budget_bytes=8<<30))
    t=time.perf_counter(); c=time.process_time(); lu=la.lu_factor(A); la.lu_solve(lu,b); print('dense LU+solve wall %.2f cpu %.2f'%(time.perf_counter()-t,time.process_time()-c))
    t=time.perf_counter(); c=time.process_time(); [A@b for _ in range(10)]; print('dense matmul x10 wall %.3f cpu %.3f'%(time.perf_counter()-t,time.process_time()-c))
    print(f.event)
