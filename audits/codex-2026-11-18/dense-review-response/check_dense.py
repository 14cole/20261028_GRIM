"""Independent algebra/dispatch checks of real DenseFactor, including fallbacks."""
import sys,os,pathlib,json,numpy as np
root=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(pathlib.Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.linalg.dense import DenseFactor
from ghost_backend.execution.options import execution_scope
from ghost_backend.linalg.refined_lu import linear_precision
import ghost_backend.twod.solver as solver
rng=np.random.default_rng(72183);n=96
a=rng.normal(size=(n,n))+1j*rng.normal(size=(n,n));a+=n*np.eye(n)
x=rng.normal(size=(n,180))+1j*rng.normal(size=(n,180));b=a@x
records=[];arrays={}
for order in ('C','F','strided'):
 source=np.array(a,order='F' if order=='F' else 'C')
 if order=='strided':
  backing=np.zeros((2*n,2*n),complex);backing[::2,::2]=source;source=backing[::2,::2]
 original=source.copy()
 with execution_scope(dict(factorization='dense',dense_residual_storage='memory',blas_threads=1,ram_budget_gib=4)):
  fac=DenseFactor(source,diagnostics={})
  for width in (1,2,9,17,180):
   for layout in ('C','F','strided','vector'):
    if layout=='vector' and width!=1:continue
    rhs=np.array(b[:,:width],order='F' if layout=='F' else 'C')
    if layout=='strided':
     backing=np.zeros((n,2*width),complex);backing[:,::2]=rhs;rhs=backing[:,::2]
    if layout=='vector':rhs=rhs[:,0]
    saved=rhs.copy();sol=fac.solve(rhs);wanted=x[:,0] if layout=='vector' else x[:,:width]
    err=float(np.linalg.norm(sol-wanted)/np.linalg.norm(wanted));assert err<1e-12
    assert np.array_equal(rhs,saved) and np.array_equal(source,original)
    key=f'{order}-{width}-{layout}';arrays[key]=sol;records.append(dict(case=key,relative_error=err))
  assert np.count_nonzero(fac.solve(np.zeros((n,3),complex)))==0
  for bad in (np.full((n,1),np.nan),np.full((n,1),np.inf),np.zeros((n,0)),np.zeros((n+1,1))):
   try:fac.solve(bad)
   except ValueError:pass
   else:raise AssertionError('Invalid RHS admitted')
  # Force an inaccurate first inverse application to exercise refinement.
  inverse=fac._apply_inverse;calls=[0]
  def inaccurate(rhs,return_residual=False):
   calls[0]+=1;answer=inverse(rhs,return_residual)
   if calls[0]==1:
    if return_residual:return answer[0]*1.001,answer[1]
    return answer*1.001
   return answer
  fac._apply_inverse=inaccurate;sol=fac.solve(b[:,:2]);assert calls[0]>1 and np.linalg.norm(sol-x[:,:2])/np.linalg.norm(x[:,:2])<1e-12
  fac._apply_inverse=inverse
  # Nonfinite output must fail the physical gate even with finite input.
  fac._apply_inverse=lambda rhs,return_residual=False:(np.full_like(rhs,np.nan),None) if return_residual else np.full_like(rhs,np.nan)
  try:fac.solve(b[:,:1])
  except RuntimeError:pass
  else:raise AssertionError('Nonfinite solution admitted')
  fac.close()
for mode in ('disk','mixed','numpy','custom','hierarchical'):
 with execution_scope(dict(factorization='hierarchical' if mode=='hierarchical' else 'dense',dense_residual_storage='disk' if mode=='disk' else 'memory',blas_threads=1,ram_budget_gib=4)),linear_precision('mixed' if mode=='mixed' else 'double'):
  source=np.array(a,order='F');old=solver._SCIPY_LINALG
  try:
   if mode=='numpy':solver._SCIPY_LINALG=None
   fac=DenseFactor(source,diagnostics=None if mode=='numpy' else {},owned_matrix=True)
   if mode=='disk':assert fac._residual_spool is not None
   if mode=='mixed':assert fac.mixed is not None
   if mode=='hierarchical':assert fac.hierarchical is not None
   calls=[0]
   if mode=='custom':
    class Wrapped:
     def __len__(self):return len(a)
     def __matmul__(self,rhs):calls[0]+=1;return a@rhs
    fac.a=Wrapped()
   sol=fac.solve(b);err=float(np.linalg.norm(sol-x)/np.linalg.norm(x));assert err<1e-11
   if mode=='custom':assert calls[0]>0
   if mode=='disk':fac.restore_original();assert np.array_equal(source,a)
   records.append(dict(case=mode,relative_error=err));arrays[mode]=sol;fac.close()
  finally:solver._SCIPY_LINALG=old
out=pathlib.Path(sys.argv[2]);out.with_suffix('.json').write_text(json.dumps(records,indent=2));np.savez_compressed(out.with_suffix('.npz'),**arrays)
print('PASS',len(records),'solution cases plus zero/invalid/nonfinite/refinement and input-preservation checks')
