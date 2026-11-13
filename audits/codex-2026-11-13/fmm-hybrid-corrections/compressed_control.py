"""Existing production HMatrixOperator/HMatrixFactor control on the same mesh.
Uses production tolerances, inverse refinement and exact sample-row release
checks. No relaxed preconditioner subclass and no FMM. No mesh/condition gate.
"""
import os,sys,json,time,resource
import numpy as np
sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup')+'/tools/GHOST')
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
from ghost_backend.compressed.coefficients import NativeOracle
from ghost_backend.compressed.hmatrix import HMatrixOperator,support_radius
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
from ghost_backend.twod.formulations import dielectric
from ghost_backend.twod import operators as op
from fmm_galerkin import circle_mesh
from types import SimpleNamespace
spec=json.loads(sys.argv[1]);n=spec['n'];k0=spec['k'];pol=spec.get('pol','TE');eps=complex(*spec.get('eps',[3.,-.08]));k1=k0*np.sqrt(eps)
mesh=circle_mesh(n,star=True,inward=True);angles=np.array([0.,47.]);obs=np.arange(0.,360.,2.)
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k1,k_minus=k0,plus_region=1,minus_region=0)
start=time.perf_counter();rss=lambda:resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 coords=np.tile(np.asarray([node.xy for node in mesh.nodes]),(2,1))
 oracle=NativeOracle(mesh,[info],pol,k0,'dielectric')
 t=time.perf_counter();h=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=4*2**30);assembly=time.perf_counter()-t
 print(json.dumps(dict(stage='operator',seconds=assembly,bytes=h.bytes,peak_gib=rss())),file=sys.stderr,flush=True)
 t=time.perf_counter();f=HMatrixFactor(h,storage_budget_bytes=4*2**30);factor_seconds=time.perf_counter()-t
 print(json.dumps(dict(stage='factor',seconds=factor_seconds,bytes=f.factor.bytes,peak_gib=rss())),file=sys.stderr,flush=True)
 b=dielectric.rhs_many(mesh,k0,angles);t=time.perf_counter();x=f.solve(b);solve_seconds=time.perf_counter()-t;peak=rss()
 field=op._farfield_linear_density_many(mesh,x[:n],k0,obs,'DLP',projection='grid')+1j*k0*op._farfield_linear_density_many(mesh,x[:n],k0,obs,'SLP',projection='grid')
 np.savez_compressed(spec['out']+'.npz',density=x,field=field,rhs=b,angles=angles,observation=obs)
 print(json.dumps(dict(spec,assembly_seconds=assembly,factor_seconds=factor_seconds,solve_seconds=solve_seconds,peak_solve_gib=peak,operator_bytes=h.bytes,inverse_bytes=f.factor.bytes,
    event=f.event,operator_evidence=h.evidence,wall_seconds=time.perf_counter()-start,physical_and_sampled_residual_checks=True,mesh_and_condition_certification=False)),flush=True)
