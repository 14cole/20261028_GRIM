"""Direct-BLAS dispatch, ownership and wrapper-allocation checks."""
import sys,pathlib,json,tracemalloc,numpy as np
sys.path.insert(0,str(pathlib.Path(sys.argv[1])/'tools/GHOST'))
import scipy.linalg as la
from ghost_backend.linalg.dense import DenseFactor
from ghost_backend.execution.options import execution_scope
rng=np.random.default_rng(918);records=[]
with execution_scope(dict(factorization='dense',dense_residual_storage='memory',blas_threads=1,ram_budget_gib=4)):
 for matrix_order in ('C','F'):
  a=np.array(np.eye(80)*80+rng.normal(size=(80,80))+1j*rng.normal(size=(80,80)),order=matrix_order)
  for rhs_order in ('C','F','strided'):
   for width in (1,2,16,17,180):
    f=DenseFactor(a);original_inverse=f._apply_inverse
    def reordered(b,return_residual=False):
     ans=original_inverse(b,return_residual)
     x,res=ans if return_residual else (ans,None)
     x=np.array(x,order='F' if rhs_order=='F' else 'C')
     if rhs_order=='strided':
      backing=np.empty((2*len(x),x.shape[1]),complex);backing[::2]=x;x=backing[::2]
     return (x,res) if return_residual else x
    f._apply_inverse=reordered
    rhs=rng.normal(size=(80,width))+1j*rng.normal(size=(80,width));a0=a.copy();b0=rhs.copy();calls=[];original=la.blas.zgemm
    def checked(alpha,aa,xx):
     assert aa is f.a and aa.flags.f_contiguous and xx.flags.f_contiguous
     assert aa.dtype==xx.dtype==np.complex128 and xx.shape[1]>1
     result=original(alpha,aa,xx);assert not np.shares_memory(result,aa) and not np.shares_memory(result,xx)
     calls.append(xx.shape[1]);return result
    try:la.blas.zgemm=checked;answer=f.solve(rhs)
    finally:la.blas.zgemm=original
    expected=matrix_order=='F' and rhs_order=='F' and width>1
    assert bool(calls)==expected,(matrix_order,rhs_order,width,calls)
    assert np.array_equal(a,a0) and np.array_equal(rhs,b0)
    assert np.linalg.norm(a@answer-rhs)/np.linalg.norm(rhs)<1e-12
    records.append(dict(matrix=matrix_order,candidate=rhs_order,width=width,calls=len(calls)));f.close()
# The guarded wrapper must not allocate an extra n-by-n conversion.
n=1536;a=np.asfortranarray(rng.normal(size=(n,n))+1j*rng.normal(size=(n,n)));x=np.asfortranarray(rng.normal(size=(n,16))+1j*rng.normal(size=(n,16)))
tracemalloc.start();y=la.blas.zgemm(1.,a,x);current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
assert peak<y.nbytes+1024**2,(peak,y.nbytes)
out=dict(dispatch=records,allocation=dict(matrix_bytes=a.nbytes,result_bytes=y.nbytes,traced_peak_bytes=peak,native_blas_workspace_measured=False))
pathlib.Path(sys.argv[2]).write_text(json.dumps(out,indent=2));print('PASS',len(records),'dispatch cases; no traced full matrix conversion')
