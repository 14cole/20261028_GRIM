import sys, os, time
sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
import numpy as np, scipy.linalg as la
from ghost_backend.linalg.dense import DenseFactor
from ghost_backend.linalg import sweep
from ghost_backend.execution.options import execution_scope, DEFAULTS
from e5_lib import kernel, circle
n=2000; w=2*np.pi/n; xy=circle(n); ka=30.
A=kernel(xy,ka,w)+0.5*np.eye(n)
ang=np.linspace(0,2*np.pi,512,endpoint=False)
B=np.exp(1j*ka*(xy[:,0:1]*np.cos(ang)[None]+xy[:,1:2]*np.sin(ang)[None]))
lu=la.lu_factor(A)
ninf=np.abs(A).sum(1).max()
def be(X,B): return (np.abs(A@X-B).max(0)/(ninf*np.abs(X).max(0)+np.abs(B).max(0)))
for hier in ('0','1'):
    os.environ['GHOST_HIERARCHICAL_MIN_UNKNOWNS']=hier
    for setting in ('off','auto','on'):
        with execution_scope(dict(DEFAULTS,blas_threads=1)):
            f=DenseFactor(A.copy(),None,'t',coordinates=xy)
            st=sweep.SweepBasis(256)
            t=time.process_time(); X=[]
            for s in range(0,512,256): X.append(sweep.solve(f,B[:,s:s+256],st,setting=setting))
            X=np.hstack(X); dt=time.process_time()-t
            Xr=la.lu_solve(lu,B)
            ev=f.event['sweep_compression']
            print('hier',hier,setting,'cpu %.2fs'%dt,'max be %.1e'%be(X,B).max(),'max rel err vs LU %.1e'%(np.linalg.norm(X-Xr,axis=0)/np.linalg.norm(Xr,axis=0)).max(),
                  {k:ev[k] for k in ('input_columns','solved_columns','accepted_batches','fallback_batches','fallback_columns','retained_basis_columns','reused_basis_batches','max_rhs_error','max_reconstructed_backward_error')}, {k:v for k,v in ev.items() if 'batches' in k and k not in('accepted_batches','fallback_batches','reused_basis_batches')})
# adversarial: one tiny column and one exactly-zero column, one column outside the span
os.environ['GHOST_HIERARCHICAL_MIN_UNKNOWNS']='0'
rng=np.random.default_rng(0)
B2=B[:,:256].copy(); B2[:,17]=1e-13*(rng.standard_normal(n)+1j*rng.standard_normal(n)); B2[:,40]=0; B2[:,99]*=1e9
with execution_scope(dict(DEFAULTS,blas_threads=1)):
    f=DenseFactor(A.copy(),None,'t',coordinates=xy)
    X=sweep.solve(f,B2,sweep.SweepBasis(256),setting='on')
    Xr=la.lu_solve(lu,B2)
    rel=np.linalg.norm(X-Xr,axis=0)/np.maximum(np.linalg.norm(Xr,axis=0),1e-300)
    ev=f.event['sweep_compression']
    print('adversarial on: tiny col rel err %.1e be %.1e | zero col max|x| %.1e | scaled col rel err %.1e | worst other %.1e'%(rel[17],be(X,B2)[17],np.abs(X[:,40]).max(),rel[99],np.delete(rel,[17,40,99]).max()),
          {k:ev[k] for k in ('solved_columns','accepted_batches','fallback_batches','fallback_columns','max_rhs_error','max_reconstructed_backward_error')})
