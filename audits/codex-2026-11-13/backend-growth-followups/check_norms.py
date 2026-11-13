"""Norm reductions, scaling contracts and thread independence on mixed blocks."""
import os,sys,json,types
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST')
from ghost_backend.compressed.hmatrix import HMatrixOperator,BlockRow
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
from legacy_norms import LegacyNorms
rng=np.random.default_rng(984);n=768
u=rng.normal(size=(n,7))+1j*rng.normal(size=(n,7));v=rng.normal(size=(7,n))+1j*rng.normal(size=(7,n));a=np.eye(n)*8+u@v/n
class Oracle:
 def __init__(self):self.n=n
 def get_with_error(self,r,c):return a[np.ix_(r,c)].copy(),np.zeros((len(r),len(c)))
coords=np.c_[np.linspace(0,1,n),np.zeros(n)];records=[];arrays={}
with cpu_allocation_scope(4),execution_scope({'assembly_threads':1,'blas_threads':1}):h=HMatrixOperator(Oracle(),coords,leaf=64,budget=2**30)
assert h.near and h.far
# Materialize one admissible block to exercise the dense-far representation.
r=h.far.pop();h.dense_far.append(BlockRow(r.row,r.start,r.stop,r.ranges,r.values(),None,2));h._index()
for scale in ['uniform','variable']:
 h.compression_rows=np.ones(n) if scale=='uniform' else np.exp(rng.uniform(-12,12,n))
 h.compression_columns=np.ones(n) if scale=='uniform' else np.exp(rng.uniform(-12,12,n))
 for workers in [1,4]:
  with execution_scope({'assembly_threads':workers,'blas_threads':1}),cpu_allocation_scope(4):
   h._absolute=types.MethodType(LegacyNorms._absolute,h);LegacyNorms._norms(h)
   ref={key:np.asarray(getattr(h,key)).copy() for key in ['row_norm','row_max','column_norm','dimensionless_norms']}
   h._absolute=types.MethodType(HMatrixOperator._absolute,h);HMatrixOperator._norms(h)
   for key,value in ref.items():assert np.array_equal(value,getattr(h,key)),(key,workers,scale)
   combined=h._absolute(dimensionless=True,include_dimensionless=True)
   assert np.array_equal(combined[0],combined[4]) and np.array_equal(combined[2],combined[5])
   full=h.get(np.arange(n),np.arange(n));direct=np.sum(abs(full),axis=1)
   assert np.allclose(h.row_norm,direct,rtol=2e-15,atol=0)
   if scale=='variable':
    scaled=abs(full)*h.compression_rows[h.position,None]*h.compression_columns[None,h.position]
    expected=np.array([scaled.sum(axis=1).max(),scaled.sum(axis=0).max()])
    assert np.allclose(h.dimensionless_norms,expected,rtol=2e-15,atol=0)
   arrays[f'{scale}-{workers}']=np.r_[h.row_norm,h.column_norm,h.row_max,h.dimensionless_norms]
   records.append(dict(scale=scale,workers=workers,bitwise_old_new=True,full_matrix_norm_check=True))
assert np.array_equal(arrays['uniform-1'],arrays['uniform-4']);assert np.array_equal(arrays['variable-1'],arrays['variable-4'])
np.savez_compressed('results/norms-contracts.npz',**arrays)
Path('results/norms-contracts.json').write_text(json.dumps(records,indent=2))
