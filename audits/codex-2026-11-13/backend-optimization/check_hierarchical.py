import os,sys,json,time,resource
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST')
from ghost_backend.linalg.hierarchical import HierarchicalFactor
from ghost_backend.compressed.hmatrix import HMatrixOperator
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
spec=json.loads(sys.argv[1]);rng=np.random.default_rng(1874);n=768
coords=np.c_[np.linspace(0,1,n),np.zeros(n)]
u=rng.normal(size=(n,8))+1j*rng.normal(size=(n,8));v=rng.normal(size=(8,n))+1j*rng.normal(size=(8,n))
a=np.eye(n,dtype=complex)*8+u@v/n
class Oracle:
 def __init__(self): self.n=n
 def get_with_error(self,r,c):return a[np.ix_(r,c)].copy(),np.zeros((len(r),len(c)))
b=rng.normal(size=(n,3))+1j*rng.normal(size=(n,3));checks=[];arrays={'matrix':a,'rhs':b}
with cpu_allocation_scope(4),execution_scope({'assembly_threads':spec.get('threads',1),'blas_threads':1}):
 h=HMatrixOperator(Oracle(),coords,leaf=64,budget=2**30)
 f=HMatrixFactor(h,storage_budget_bytes=2**30)
 dense=HierarchicalFactor(a,coords)
 for trans in [0,1,2]:
  exact=[a,a.T,a.conj().T][trans]
  for name,factor in [('compressed',f),('dense_hodlr',dense)]:
   x=factor.inverse(b,trans=trans) if name=='compressed' else factor.solve(b,trans=trans)
   error=np.linalg.norm(exact@x-b,np.inf)/(np.linalg.norm(exact,np.inf)*np.linalg.norm(x,np.inf)+np.linalg.norm(b,np.inf));assert error<1e-12
   arrays[f'{name}_{trans}']=x
   checks.append(dict(method=name,trans=trans,backward_error=error))
  for width in [1,3]:
   y=h.matmul(b[:,:width],trans=trans);error=np.linalg.norm(y-exact@b[:,:width])/np.linalg.norm(exact@b[:,:width]);assert error<1e-11
   arrays[f'product_{trans}_{width}']=y
  for empty in [False,True]:
   rr=rng.permutation(n)[:137 if not empty else 0];cc=rng.permutation(n)[:229]
   block=a[np.ix_(rr,cc)];target=[block,block.T,block.conj().T][trans]
   q=rng.normal(size=(target.shape[1],2))+1j*rng.normal(size=(target.shape[1],2))
   z=h.block_matmul(rr,cc,q,trans=trans);ref=target@q
   error=np.linalg.norm(z-ref)/max(np.linalg.norm(ref),1e-300);assert error<1e-11
   arrays[f'block_{trans}_{empty}']=z
  # In-place inverse tree use, important to nested transpose/adjoint recursion.
  for name,node,perm in [('compressed',f.factor.root,f.factor.permutation),('dense',dense.root,dense.permutation)]:
   x=b[perm].copy();ref=node.solve(x,trans);node.solve_into(x,x,trans);assert np.array_equal(x,ref)
np.savez_compressed(spec['out']+'.npz',**arrays)
print(json.dumps(dict(spec,checks=checks,peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20)))
