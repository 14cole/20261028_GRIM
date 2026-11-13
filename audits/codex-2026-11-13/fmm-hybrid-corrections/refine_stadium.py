"""Isolate the mixed-geometry maximum-entry error without rebuilding near data.
For each full matrix, replace only the far contribution: A_new=A_old-F_old+F_new.
Also independently integrate the worst K entry's four supporting panel pairs.
"""
import os,sys,json
import numpy as np
sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup')+'/tools/GHOST')
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
from review_geometry import mesh_from_loops
from hybrid_galerkin import NearOracle
from nodal_block import NodalBlock
from moment_galerkin import MomentFar

n=1536;k=40-.8j
th=np.linspace(-np.pi/2,np.pi/2,n//4,endpoint=False)
arc=np.column_stack((1+np.cos(th),np.sin(th)));top=np.column_stack((np.linspace(1,-1,n//4,endpoint=False),np.ones(n//4)))
mesh=mesh_from_loops([np.vstack((arc,top,-arc,-top))[::-1]],19)
def full(far,kind):
 out=np.empty((n,n),complex)
 for start in range(0,n,48):
  ids=np.arange(start,min(n,start+48));x=np.zeros((n,len(ids)),complex);x[ids,np.arange(len(ids))]=1
  out[:,ids]=far.apply(x,kind)
 return out
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 oracle=NearOracle(mesh,k);old=MomentFar(oracle.g,k,digits=10)
 arrays={kd:dict(np.load('results/matrix-stadium-1536-'+kd+'.npz')) for kd in ['S','K','KP','W']}
 out={'diagnostics':{},'digits':{}}
 for kd in ['K','KP']:
  d=arrays[kd];ref=d['reference_rows'];a=d['actual_matrix'];r,c=np.unravel_index(np.argmax(abs(a-ref)),a.shape)
  v=NodalBlock(oracle,np.arange(n),np.arange(n)).fetch(np.array([r if kd=='K' else c]),np.array([c if kd=='K' else r]))[1][0,0]
  out['diagnostics'][kd]=dict(row=int(r),col=int(c),absolute_error=float(abs(a[r,c]-ref[r,c])),reference_magnitude=float(abs(ref[r,c])),
     joint_direct_vs_reference=float(abs(v-ref[r,c])),joint_direct_vs_fmm=float(abs(v-a[r,c])))
  print(kd,out['diagnostics'][kd],file=sys.stderr,flush=True)
 for kd,d in arrays.items():
  d['near_only']=d['actual_matrix']-full(old,kd)
 for digits in [12,14]:
  far=MomentFar(oracle.g,k,digits=digits);res={}
  for kd,d in arrays.items():
   a=d['near_only']+full(far,kd);ref=d['reference_rows'];err=abs(a-ref)
   res[kd]=dict(relative_max=float(err.max()/abs(ref).max()),relative_fro=float(np.linalg.norm(a-ref)/np.linalg.norm(ref)))
   # Complete products plus all worst columns retained, full matrices reproducible.
   cols=np.unique(np.unravel_index(np.argpartition(err.ravel(),-32)[-32:],err.shape)[1])
   np.savez_compressed(f'results/stadium-digits{digits}-{kd}.npz',columns=cols,actual=a[:,cols],reference=ref[:,cols],input=d['input'],product=a@d['input'],exact_product=ref@d['input'])
  out['digits'][str(digits)]=res;print(digits,res,file=sys.stderr,flush=True)
 print(json.dumps(out),flush=True)
