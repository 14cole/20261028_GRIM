"""Native wideband FMM control on columns containing the diagonal FMM's worst entries."""
import os,sys,json,time
import numpy as np
sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup')+'/tools/GHOST')
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
from review_geometry import mesh_from_loops
from fmm_galerkin import GalerkinFMM
n=1536;k=40-.8j
th=np.linspace(-np.pi/2,np.pi/2,n//4,endpoint=False)
arc=np.column_stack((1+np.cos(th),np.sin(th)));top=np.column_stack((np.linspace(1,-1,n//4,endpoint=False),np.ones(n//4)))
mesh=mesh_from_loops([np.vstack((arc,top,-arc,-top))[::-1]],19)
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 t=time.perf_counter();g=GalerkinFMM(mesh,k,eps=1e-12);out={'setup_seconds':time.perf_counter()-t,'operators':{}}
 for kind in ['K','KP']:
  d=np.load('results/matrix-stadium-1536-'+kind+'.npz');ref=d['reference_rows'];old=d['actual_matrix'];err=abs(old-ref)
  r,c=np.unravel_index(np.argmax(err),err.shape)
  cols=np.unique(np.unravel_index(np.argpartition(err.ravel(),-16)[-16:],err.shape)[1])
  x=np.zeros((n,len(cols)),complex);x[cols,np.arange(len(cols))]=1
  out['operators'][kind]={'columns':cols.tolist(),'row':int(r),'col':int(c),'eps':{}}
  for eps in [1e-12,1e-14]:
   g.eps=eps;t=time.perf_counter();y=g.apply(x,kind);seconds=time.perf_counter()-t
   out['operators'][kind]['eps'][str(eps)]=dict(seconds=seconds,selected_column_relative_max=float(np.max(abs(y-ref[:,cols]))/np.max(abs(ref))),target_absolute_error=float(abs(y[r,np.searchsorted(cols,c)]-ref[r,c])))
   np.savez_compressed(f'results/native-stadium-{kind}-{eps}.npz',columns=cols,actual=y,reference=ref[:,cols])
 print(json.dumps(out),flush=True)
