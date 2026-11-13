"""Production DenseFactor control on the same fixed P1 dielectric mesh.
No mesh/condition certification is timed in either this control or the FMM
research solve. DenseFactor's physical and scaled residual checks remain on.
"""
import os,sys,json,time,resource
import numpy as np
from pathlib import Path
sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup')+'/tools/GHOST')
from ghost_backend.execution.cpu import CPUState, _STATE
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
from ghost_backend.twod.formulations import dielectric
from ghost_backend.twod import operators as op
from ghost_backend.linalg.dense import DenseFactor
from fmm_galerkin import circle_mesh
from types import SimpleNamespace
spec=json.loads(sys.argv[1]);n=spec['n'];k0=spec['k'];pol=spec.get('pol','TE');eps=complex(*spec.get('eps',[3.,-.08]));k1=k0*np.sqrt(eps)
mesh=circle_mesh(n,star=True,inward=True);angles=np.array([0.,47.]);obs=np.arange(0.,360.,2.)
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k1,k_minus=k0,plus_region=1,minus_region=0)
state=CPUState(kernel_only=True);state.reuse_operators=False
start=time.perf_counter();rss=lambda:resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20
with _STATE.override(state),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1,'dense_residual_storage':'memory'}):
 t=time.perf_counter();a=dielectric.assemble_system(mesh,[info],pol,k0);assembly=time.perf_counter()-t
 print(json.dumps(dict(stage='dense_assembled',seconds=assembly,peak_gib=rss())),file=sys.stderr,flush=True)
 t=time.perf_counter();f=DenseFactor(a,owned_matrix=True,force_double=True);factor_seconds=time.perf_counter()-t
 assert f.hierarchical is None and f.mixed is None
 print(json.dumps(dict(stage='dense_factored',seconds=factor_seconds,peak_gib=rss())),file=sys.stderr,flush=True)
 b=dielectric.rhs_many(mesh,k0,angles);t=time.perf_counter();x=f.solve(b);solve_seconds=time.perf_counter()-t
 peak=rss()
 field=op._farfield_linear_density_many(mesh,x[:n],k0,obs,'DLP',projection='grid')+1j*k0*op._farfield_linear_density_many(mesh,x[:n],k0,obs,'SLP',projection='grid')
 np.savez_compressed(spec['out']+'.npz',density=x,field=field,rhs=b,angles=angles,observation=obs)
 result=dict(spec,assembly_seconds=assembly,factor_seconds=factor_seconds,solve_seconds=solve_seconds,peak_solve_gib=peak,event=f.event,wall_seconds=time.perf_counter()-start,
     matrix_bytes=a.nbytes,lu_bytes=f.lu.nbytes,physical_and_scaled_residual_checks=True,mesh_and_condition_certification=False)
 prior=Path('results/pre-4096-TE-loose.npz')
 if prior.exists() and n==4096 and k0==80 and pol=='TE':
  with np.load(prior) as z:fx=z['density']
  assert not np.shares_memory(a,f.lu)
  residual=a@fx-b;rows,cols,norm=f._condition_scaling
  physical=np.max(abs(residual),axis=0)/(f.matrix_inf*np.max(abs(fx),axis=0)+np.max(abs(b),axis=0))
  scaled=np.sum(abs(residual)/rows[:,None],axis=0)/(norm*np.sum(abs(fx)*cols[:,None],axis=0)+np.sum(abs(b)/rows[:,None],axis=0))
  result['fmm_full_physical_backward_error']=physical.tolist()
  result['fmm_full_scaled_backward_error']=scaled.tolist()
  result['fmm_full_relative_residual']=(np.linalg.norm(residual,axis=0)/np.linalg.norm(b,axis=0)).tolist()
  np.savez_compressed(spec['out']+'-fmm-residual.npz',residual=residual,rhs=b,density=fx,row_scale=rows,column_scale=cols,matrix_inf=f.matrix_inf,scaled_norm_1=norm)
  assert max(physical.max(),scaled.max())<1e-12
 result['kernel_tables']=state.table_events;result['peak_complete_gib']=rss()
 print(json.dumps(result),flush=True)
