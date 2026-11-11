"""Isolated double versus mixed LU with exact double on-disk residuals.
This is NOT integrated into the production solver or its admission machinery.
"""
import sys,json,time,resource
from pathlib import Path
import numpy as np
from scipy.linalg import lu_factor,lu_solve
root,prefix,method=sys.argv[1:4];sys.path.insert(0,str(Path(root)/'tools/GHOST'))
from ghost_backend.linalg.refined_lu import RefinedLU
n=json.loads(Path(prefix+'-info.json').read_text())['n'];b=np.load(prefix+'-rhs.npy')
if b.ndim==1:b=b[:,None]
block_rows=64;started=time.perf_counter();corrections=[]
def blocks():
 with open(prefix+'-matrix.raw','rb') as f:
  for start in range(0,n,block_rows):
   stop=min(n,start+block_rows);a=np.fromfile(f,dtype=np.complex128,count=(stop-start)*n)
   if a.size!=(stop-start)*n:raise OSError('Incomplete matrix')
   yield start,stop,a.reshape(stop-start,n)
def dense(dtype):
 a=np.empty((n,n),dtype=dtype,order='F')
 for start,stop,block in blocks():a[start:stop]=block
 return a
def product(x,trans=0):
 y=np.zeros((n,x.shape[1]),np.complex128)
 for start,stop,a in blocks():
  if trans==0:y[start:stop]=a@x
  elif trans==1:y+=a.T@x[start:stop]
  else:y+=a.conj().T@x[start:stop]
 return y
matrix_inf=max(float(np.max(np.sum(abs(a),axis=1))) for _,_,a in blocks())
error=None;results=[];refined=None
try:
 if method=='mixed-memory':
  a=dense(np.complex128);refined=RefinedLU(a);lu,piv=refined.lu,refined.piv
 else:
  a=dense(np.complex64 if method=='mixed-spool' else np.complex128)
  lu,piv=lu_factor(a,overwrite_a=True,check_finite=False);assert np.shares_memory(lu,a)
 for trans in (0,1,2):
  t=time.perf_counter()
  if refined is not None:
   x=refined.solve(b,trans=trans);steps=refined.max_corrections
  else:
   x=lu_solve((lu,piv),b.astype(lu.dtype),trans=trans,check_finite=False).astype(np.complex128)
   previous=float('inf');steps=0
   if method=='mixed-spool':
    for step in range(10):
     residual=b-product(x,trans);rel=float(np.max(np.max(abs(residual),axis=0)/np.maximum(np.max(abs(b),axis=0),1e-300)))
     if np.isfinite(rel) and rel<=2e-12:steps=step;break
     if not np.isfinite(rel) or rel>=previous*.98:raise np.linalg.LinAlgError('Mixed refinement stalled; double fallback required')
     previous=rel
     x+=lu_solve((lu,piv),residual.astype(np.complex64),trans=trans,check_finite=False).astype(np.complex128)
    else:raise np.linalg.LinAlgError('Mixed correction limit')
  residual=product(x,trans)-b
  # Transposed systems have different infinity norms; compute the actual norm.
  if trans:
   col=np.zeros(n)
   for _,_,block in blocks():col+=np.sum(abs(block),axis=0)
   norm=float(col.max())
  else:norm=matrix_inf
  def backward_error(candidate,residual):
   return float(np.max(np.max(abs(residual),axis=0)/(norm*np.max(abs(candidate),axis=0)+np.max(abs(b),axis=0))))
  backward=backward_error(x,residual);initial_backward=backward
  if method=='double-spool':
   # Mirror production DenseFactor's two-step full-double residual correction.
   for attempt in range(2):
    if backward<=1e-12:break
    candidate=x+lu_solve((lu,piv),-residual,trans=trans,check_finite=False)
    updated=product(candidate,trans)-b;candidate_error=backward_error(candidate,updated)
    if candidate_error>=backward:break
    x,residual,backward=candidate,updated,candidate_error;steps+=1
  np.save(prefix+'-'+method+'-t'+str(trans)+'.npy',x)
  results.append(dict(trans=trans,corrections=steps,initial_backward_error=initial_backward,backward_error=backward,passes_dense_gate=backward<=1e-12,seconds=time.perf_counter()-t))
except Exception as e:error=type(e).__name__+': '+str(e)
print(json.dumps(dict(prefix=prefix,method=method,n=n,rhs_columns=b.shape[1],wall=time.perf_counter()-started,rss_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2,lu_bytes=n*n*(8 if method.startswith('mixed') else 16),retained_original_bytes=n*n*16 if method=='mixed-memory' else 0,error=error,results=results)))
