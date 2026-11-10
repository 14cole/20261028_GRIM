import sys, os, time
sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
import numpy as np, scipy.special as sp, scipy.linalg as la
from ghost_backend.compressed import hmatrix as HM
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
from ghost_backend.execution.options import execution_scope, DEFAULTS
from e5_lib import DenseOracle, kernel, circle
def eqcond(A):
    r=np.abs(A).max(1); B=A/r[:,None]; c=np.abs(B).max(0); return np.linalg.cond(B/c,1)
def run(name,A,xy,radius,seeds=(1,2,3)):
    n=len(A)
    with execution_scope(dict(DEFAULTS,assembly_threads=2,blas_threads=1)):
        try:
            op=HM.HMatrixOperator(DenseOracle(A),xy,radius,budget=8<<30)
        except Exception as e:
            print(name,'operator REJECTED',type(e).__name__,str(e)[:100]); return
        rng=np.random.default_rng(5); b=rng.standard_normal((n,6))+1j*rng.standard_normal((n,6))
        xr=la.solve(A,b)
        conds=[]
        for s in seeds:
            np.random.seed(s); st0=np.random.get_state()[1][:3].copy()
            d={}
            t=time.time()
            try:
                f=HMatrixFactor(op,d,'t',storage_budget_bytes=8<<30)
            except Exception as e:
                print(name,'factor raised',type(e).__name__,str(e)[:160]); return
            conds.append(d.get('condition_est'))
            adv=not np.array_equal(st0,np.random.get_state()[1][:3]) or np.random.get_state()[2]!=624
        tf=time.time()-t
        t=time.time()
        try: x=f.solve(b)
        except Exception as e:
            print(name,'solve raised',type(e).__name__,str(e)[:160]); return
        ts=time.time()-t
        ninf=np.abs(A).sum(1).max()
        be=(np.abs(A@x-b).max(0)/(ninf*np.abs(x).max(0)+np.abs(b).max(0))).max()
        ev=f.event
        print(name,'n',n,'factor %.1fs solve %.2fs'%(tf,ts),'TRUE backward err %.2e'%be,'rel diff vs LU %.2e'%(np.linalg.norm(x-xr)/np.linalg.norm(xr)),
              'cond est by seed',['%.6g'%c for c in conds],'exact eq cond1 %.6g'%eqcond(A),'global RNG advanced',adv,
              {k:ev.get(k) for k in ('factorizations','gmres_columns','max_refinements','refinement_steps','max_backward_error','max_sampled_backward_error','sampled_rejection','tightened_operator_tolerance','coarse_rejection')},
              'pre tol',f.tolerance,'pre bytes/dense %.3f'%(f.factor.bytes/(16*n*n)),'max inv rank',f.factor.evidence['max_rank'])
w=lambda n:2*np.pi/n
n=3000
xy=circle(n); r=np.full(n,w(n))
A=kernel(xy,40.,w(n))+0.5*np.eye(n); run('2nd kind ka=40',A,xy,r)
A=kernel(xy,40.,w(n)); run('1st kind ka=40',A,xy,r)
# interior-resonance-like: 2nd kind double-layer-free -> use near singular by SVD modification
A=kernel(xy,40.,w(n))+0.5*np.eye(n); u,s,vh=np.linalg.svd(A); s[-1]=1e-9*s[0]; run('near-singular 1e9',(u*s)@vh,xy,r)
s[-1]=1e-13*s[0]; run('near-singular 1e13',(u*s)@vh,xy,r)
