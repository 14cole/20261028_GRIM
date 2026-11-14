"""Existing production HMatrixOperator/HMatrixFactor control on the same mesh.
Uses production tolerances, inverse refinement and exact sample-row release
checks. No relaxed preconditioner subclass and no FMM. No mesh/condition gate.
"""
import os,sys,json,time,resource
import numpy as np
sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup')+'/tools/GHOST')
from ghost_backend.execution.cpu import CPUState, _STATE
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
from ghost_backend.compressed.coefficients import NativeOracle
from ghost_backend.compressed.hmatrix import HMatrixOperator,support_radius
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
from ghost_backend.twod.formulations import dielectric
from ghost_backend.twod import operators as op
from fmm_galerkin import circle_mesh
from types import SimpleNamespace
spec=json.loads(sys.argv[1]);n=spec['n'];k0=spec['k'];pol=spec.get('pol','TE');eps=complex(*spec.get('eps',[3.,-.08]));k1=k0*np.sqrt(eps)
mesh=circle_mesh(n,star=spec.get("star",True),inward=True);angles=np.array([0.,47.]);obs=np.arange(0.,360.,2.)
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k1,k_minus=k0,plus_region=1,minus_region=0)
state=CPUState(kernel_only=True);state.reuse_operators=False
if spec.get('fallback'):
 from ghost_backend.twod.assembly.native import far,near,table
 far.far_block=lambda *a,**k:None;far.tile_library=lambda:None;far.scatter_library=lambda:None
 near.ENABLED=False;table.library=lambda:None
start=time.perf_counter();rss=lambda:resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20
with _STATE.override(state),cpu_allocation_scope(spec.get('threads',1)),execution_scope({'assembly_threads':spec.get('threads',1),'blas_threads':1}):
 coords=np.tile(np.asarray([node.xy for node in mesh.nodes]),(2,1))
 oracle=NativeOracle(mesh,[info],pol,k0,'dielectric')
 from adaptive_sketch import adaptive_column_sketch
 t=time.perf_counter()
 with adaptive_column_sketch(spec.get('adaptive_sketch',False),initial_rank_cap=spec.get('initial_rank_cap')) as sketch_stats:
  h=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),leaf=spec.get('leaf'),eta=spec.get('eta',1.),budget=spec.get('storage_budget_gib',4)*2**30)
 assembly=time.perf_counter()-t
 print(json.dumps(dict(stage='operator',seconds=assembly,bytes=h.bytes,peak_gib=rss())),file=sys.stderr,flush=True)
 t=time.perf_counter();f=HMatrixFactor(h,storage_budget_bytes=spec.get('storage_budget_gib',4)*2**30);factor_seconds=time.perf_counter()-t
 print(json.dumps(dict(stage='factor',seconds=factor_seconds,bytes=f.factor.bytes,peak_gib=rss())),file=sys.stderr,flush=True)
 quantized_bytes=0
 if spec.get('quantize_inverse'):
  def shrink(node):
   global quantized_bytes
   for name in ['v12','v21','e1','e2']:
    a=getattr(node,name,None)
    if a is not None:
     packed=a.astype(np.complex64);quantized_bytes+=a.nbytes-packed.nbytes;setattr(node,name,packed)
   if not node.leaf:shrink(node.left);shrink(node.right)
  shrink(f.factor.root);f.factor.bytes-=quantized_bytes
 b=dielectric.rhs_many(mesh,k0,angles);t=time.perf_counter();x=f.solve(b);solve_seconds=time.perf_counter()-t;peak=rss()
 field=op._farfield_linear_density_many(mesh,x[:n],k0,obs,'DLP',projection='grid')+1j*k0*op._farfield_linear_density_many(mesh,x[:n],k0,obs,'SLP',projection='grid')
 extra={}; checks={}
 if spec.get('check_adjoint'):
  rng=np.random.default_rng(921);probe=rng.normal(size=(2*n,2))+1j*rng.normal(size=(2*n,2))
  extra['probe']=probe
  for trans in [1,2]:
   t=time.perf_counter()
   for repeat in range(10): y=h.matmul(probe,trans=trans)
   checks[f'product_{trans}_seconds']=(time.perf_counter()-t)/10
   extra[f'product_{trans}']=y
   t=time.perf_counter();z,residual=f.inverse(probe,trans=trans,return_residual=True)
   checks[f'inverse_{trans}_seconds']=time.perf_counter()-t
   checks[f'inverse_{trans}_physical_error']=float(np.max(f.physical_errors(z,probe,residual,trans)))
   extra[f'inverse_{trans}']=z;extra[f'residual_{trans}']=residual
 np.savez_compressed(spec['out']+'.npz',density=x,field=field,rhs=b,angles=angles,observation=obs,**extra)
 print(json.dumps(dict(spec,assembly_seconds=assembly,factor_seconds=factor_seconds,solve_seconds=solve_seconds,peak_solve_gib=peak,operator_bytes=h.bytes,inverse_bytes=f.factor.bytes,
    adaptive_sketch_evidence=sketch_stats,quantized_inverse_saved_bytes=quantized_bytes,adjoint_checks=checks,kernel_tables=state.table_events,peak_complete_gib=rss(),event=f.event,operator_evidence=h.evidence,wall_seconds=time.perf_counter()-start,physical_and_sampled_residual_checks=True,mesh_and_condition_certification=False)),flush=True)
