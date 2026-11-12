import json,sys,tempfile
from pathlib import Path
import numpy as np
import scipy.linalg as la
from threadpoolctl import threadpool_limits
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from out_of_core_lu import DiskLU,FusedDiskLU
from experiment_hooks import ScaledMixed
from ghost_backend.linalg.workspace import matrix_inf_norm
rng=np.random.default_rng(437);results=[]
with threadpool_limits(limits=1),tempfile.TemporaryDirectory() as d:
 for method,n,b in [(cls,n,b) for cls in [DiskLU,FusedDiskLU] for n,b in [(17,4),(65,16),(128,32)]]:
  a=rng.normal(size=(n,n))+1j*rng.normal(size=(n,n));a+=np.eye(n)*2
  rhs=rng.normal(size=(n,3))+1j*rng.normal(size=(n,3))
  factor=method(a,Path(d)/'lu.bin',b)
  for trans in (0,1,2):
   op=a if trans==0 else a.T if trans==1 else a.conj().T
   x=factor.solve(rhs,trans);ref=la.solve(op,rhs);err=np.max(abs(x-ref))/np.max(abs(ref));back=np.max(abs(op@x-rhs))/(matrix_inf_norm(op)*np.max(abs(x))+np.max(abs(rhs)))
   assert err<1e-10 and back<1e-12,(n,trans,err,back)
   results.append(dict(method=method.__name__,n=n,trans=trans,relative_difference=float(err),backward_error=float(back)))
  factor.close()
 n=63;a=rng.normal(size=(n,n))+1j*rng.normal(size=(n,n));a+=n*np.eye(n)
 a=np.logspace(-6,6,n)[:,None]*a*np.logspace(-4,4,n)[None,:]
 factor=ScaledMixed(a)
 for trans in (0,1,2):
  op=a if trans==0 else a.T if trans==1 else a.conj().T
  # Known solutions avoid ambiguous forward accuracy for the deliberately scaled test.
  exact=rng.normal(size=(n,2))+1j*rng.normal(size=(n,2));rhs=op@exact
  x=factor.solve(rhs,trans);back=np.max(abs(op@x-rhs))/(matrix_inf_norm(op)*np.max(abs(x))+np.max(abs(rhs)))
  assert back<1e-12
  results.append(dict(method='scaled_mixed',n=n,trans=trans,backward_error=float(back),corrections=factor.max_corrections))
 # Exact singularity must be rejected by both disk implementations.
 for method in [DiskLU,FusedDiskLU]:
  try:method(np.zeros((9,9),complex),Path(d)/'singular.bin',4)
  except la.LinAlgWarning:results.append(dict(method=method.__name__,control='singular',rejected=True))
  else:raise AssertionError('Singular LU accepted')
Path(__file__).with_name('PROTOTYPE_CONTROLS.json').write_text(json.dumps(results,indent=2)+'\n');print('Passed',len(results),'prototype controls')
