"""Test the review's row_scale + include_dimensionless concern directly."""
import os,sys,json,types
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST')
from ghost_backend.compressed.hmatrix import HMatrixOperator
from legacy_norms import LegacyNorms
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
rng=np.random.default_rng(73);n=384;u=rng.normal(size=(n,5))+1j*rng.normal(size=(n,5));a=np.eye(n)+u@u.conj().T/n
class Oracle:
 def __init__(self):self.n=n
 def get_with_error(self,r,c):return a[np.ix_(r,c)].copy(),np.zeros((len(r),len(c)))
records=[]
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 h=HMatrixOperator(Oracle(),np.c_[np.linspace(0,1,n),np.zeros(n)],leaf=64,budget=2**30)
 h.compression_rows=np.exp(rng.uniform(-8,8,n));h.compression_columns=np.exp(rng.uniform(-8,8,n))
 for row_scale in [np.ones(n),np.exp(rng.uniform(-8,8,n))]:
  together=h._absolute(row_scale=row_scale,include_dimensionless=True)
  plain=LegacyNorms._absolute(h,row_scale=row_scale)
  dimensionless=LegacyNorms._absolute(h,row_scale=row_scale,dimensionless=True)
  assert all(np.array_equal(x,y) for x,y in zip(together[:4],plain))
  assert np.array_equal(together[4],dimensionless[0]) and np.array_equal(together[5],dimensionless[2])
  records.append(dict(bitwise_plain=True,bitwise_dimensionless=True,semantics='dimensionless norms of the row-scaled matrix'))
Path('results/norm-scope.json').write_text(json.dumps(records,indent=2))
