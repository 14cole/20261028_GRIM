"""Build/use/release mixed-storage preconditioners against a known full matrix."""
import os,sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST')
from ghost_backend.compressed import hmatrix as hm
from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
from preconditioner_storage import packed_operator_blocks,finish_operator
rng=np.random.default_rng(73);n=768;u=rng.normal(size=(n,7))+1j*rng.normal(size=(n,7));v=rng.normal(size=(7,n))+1j*rng.normal(size=(7,n));a=8*np.eye(n)+u@v/n;saved=a.copy();coords=np.c_[np.linspace(0,1,n),np.zeros(n)]
class Oracle:
 def __init__(self):self.n=n
 def get_with_error(self,r,c):return a[np.ix_(r,c)].copy(),np.zeros((len(r),len(c)))
class Pre(hm.HMatrixOperator):
 def _validate(self):
  try:super()._validate()
  except hm.HMatrixRejected:
   assert max(self.sampled_row_error,self.scaled_sampled_row_error)<1e-5
base=hm.BlockRow;out={};b=rng.normal(size=(n,2))+1j*rng.normal(size=(n,2))
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 for packed in [False,True]:
  with packed_operator_blocks(packed) as stats:h=Pre(Oracle(),coords,leaf=64,budget=2**30)
  assert hm.BlockRow is base;finish_operator(h,stats);assert h.bytes==h.ledger.bytes
  inv=HMatrixSystem(h,coords,tolerance=.01,budget=2**30,checkpoint=None);checks=[]
  complex_arrays=[];seen=set()
  def visit(value):
   if id(value) in seen:return
   seen.add(id(value))
   if isinstance(value,np.ndarray):
    if np.iscomplexobj(value):complex_arrays.append(str(value.dtype));assert value.dtype==np.complex128
   elif isinstance(value,(list,tuple)):
    for child in value:visit(child)
   elif hasattr(value,'__dict__'):
    for child in vars(value).values():visit(child)
  visit(inv.root);assert complex_arrays
  for trans,mat in enumerate([a,a.T,a.conj().T]):
   x=inv.apply(b,solve=True,trans=trans);err=float(np.linalg.norm(mat@x-b,np.inf)/(np.linalg.norm(mat,np.inf)*np.linalg.norm(x,np.inf)+np.linalg.norm(b,np.inf)))
   assert x.dtype==np.complex128 and err<1e-6;checks.append(err)
  out[str(packed)]=dict(storage=stats,backward_errors=checks,operator_bytes=h.bytes,inverse_complex_arrays=len(complex_arrays),inverse_dtype='complex128')
 assert np.array_equal(a,saved)
 # Rejection restores the class even when casting overflows or underflows.
 for value in [1e200,1e-200]:
  try:
   with packed_operator_blocks(True):hm.BlockRow(0,0,1,[(0,1)],np.array([[value]],complex),None,0)
  except (ValueError,FloatingPointError):pass
  else:raise AssertionError('Unrepresentable input accepted')
  assert hm.BlockRow is base
# Only kind=0 was reserved before the pack; kinds 1/2 reserve packed nbytes.
with packed_operator_blocks(True) as stats:
 for kind in [0,1,2]:
  u=np.ones((16,3 if kind==1 else 24),complex);v=np.ones((3,24),complex) if kind==1 else None
  prior=stats['saved_bytes'];row=hm.BlockRow(0,0,16,[(0,24)],u,v,kind)
  if kind==0:expected=stats['saved_bytes']-prior
 assert stats['near_overreservation']==expected
out['block_kinds']=dict(near_only_overreservation=True,**stats)
Path('results/storage-contracts.json').write_text(json.dumps(out,indent=2))
