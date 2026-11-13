"""Full physical/scaled residuals after timing; validation peak is separate."""
import os,sys,json,time,resource
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup')+'/tools/GHOST')
from ghost_backend.execution.cpu import CPUState,_STATE
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
from ghost_backend.twod.formulations import dielectric
from ghost_backend.linalg.workspace import equilibrated_scaling_and_norm_1,matrix_inf_norm
from fmm_galerkin import circle_mesh
from types import SimpleNamespace
n=4096;k0=80;eps=3-.08j;mesh=circle_mesh(n,star=True,inward=True)
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k0*np.sqrt(eps),k_minus=k0,plus_region=1,minus_region=0)
state=CPUState(kernel_only=True);state.reuse_operators=False
with _STATE.override(state),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 a=dielectric.assemble_system(mesh,[info],'TE',k0)
 rows,cols,norm=equilibrated_scaling_and_norm_1(a);inf=matrix_inf_norm(a)
 b=dielectric.rhs_many(mesh,k0,np.array([0.,47.]))
 reference=np.load('results/dense-production-4096.npz');result=[]
 names=['compressed-production-4096','leaf-128-4096','leaf-64-4096','eta-1.5-4096','eta-2.0-4096','quantized-inverse-4096','fmm-production-4096']
 for name in names:
  p=Path('results')/(name+'.npz')
  if not p.exists():continue
  z=np.load(p);x=z['density'];r=a@x-b
  physical=np.max(abs(r),axis=0)/(inf*np.max(abs(x),axis=0)+np.max(abs(b),axis=0))
  scaled=np.sum(abs(r)/rows[:,None],axis=0)/(norm*np.sum(abs(x)*cols[:,None],axis=0)+np.sum(abs(b)/rows[:,None],axis=0))
  field_error=np.max(abs(z['field']-reference['field']))/np.max(abs(reference['field']))
  density_error=np.max(abs(x-reference['density']))/np.max(abs(reference['density']))
  record=dict(case=name,physical=physical.tolist(),scaled=scaled.tolist(),field_error=float(field_error),density_error=float(density_error))
  assert max(physical.max(),scaled.max())<1e-12,record
  assert field_error<1e-9,record
  np.savez_compressed('results/full-residual-'+name+'.npz',residual=r,rhs=b,density=x,row_scale=rows,column_scale=cols,matrix_inf=inf,scaled_norm_1=norm)
  result.append(record)
 print(json.dumps(dict(cases=result,independent_validation_peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20,description='Separate post-timing worker; full 8192 by 8192 physical matrix, not sample rows.')),flush=True)
