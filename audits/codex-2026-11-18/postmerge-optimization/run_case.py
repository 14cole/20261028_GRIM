"""Fresh process physical solve; no monkeypatches or weakened accuracy gates."""
import os,sys,json,time,resource,hashlib,pathlib,traceback
spec=json.loads(sys.argv[1]);sys.path.insert(0,str(pathlib.Path(spec['root'])/'tools/GHOST'))
import numpy as np
from common import mesh_for,SimpleNamespace,exact_rows
from ghost_backend.execution.cpu import CPUState,_STATE
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
from ghost_backend.execution import memory_budget as mb
from ghost_backend.compressed.coefficients import NativeOracle
from ghost_backend.compressed.hmatrix import HMatrixOperator,support_radius,leaf_size
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
from ghost_backend.linalg.dense import DenseFactor
from ghost_backend.twod.formulations import dielectric,robin
from ghost_backend.twod import operators as op
import ghost_backend.twod.solver as solver

out=pathlib.Path(spec['out']);out.parent.mkdir(parents=True,exist_ok=True)
record=dict(spec=spec,stages={},rss={},error=None);start=time.perf_counter()
def rss():return int(pathlib.Path('/proc/self/status').read_text().split('VmRSS:')[1].split()[0])*1024
def stage(label,t):
 record['stages'][label]=time.perf_counter()-t;record['rss'][label]=rss()
 print(label,round(record['stages'][label],3),flush=True)
try:
 n=spec['n'];k=spec['k'];pol=spec.get('pol','TE');kind=spec.get('kind','dielectric');mesh=mesh_for(n,spec.get('geometry','star'))
 eps=3-.08j;mu=1.;info=SimpleNamespace(mu_minus=1.,mu_plus=mu,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps*mu),k_minus=k,plus_region=1,minus_region=0,robin_impedance=0.)
 infos=[info] if kind=='dielectric' else [info]*n
 nd=2*n if kind=='dielectric' else n;coords=np.tile(np.array([x.xy for x in mesh.nodes]),(2 if kind=='dielectric' else 1,1))
 oracle=NativeOracle(mesh,infos,pol,k,kind);angles=np.linspace(-90,90,180,endpoint=False)
 cpu=CPUState(kernel_only=True);cpu.reuse_operators=False
 with _STATE.override(cpu),mb.scope(wanted_gib=8) as ledger,cpu_allocation_scope(spec.get('threads',2)),execution_scope(dict(factorization='dense',assembly_threads=spec.get('threads',2),blas_threads=spec.get('blas_threads',1),ram_budget_gib=8,dense_residual_storage=spec.get('residual_storage','memory'))):
  t=time.perf_counter();dense=spec['method']=='dense'
  if dense:a=dielectric.assemble_system(mesh,infos,pol,k) if kind=='dielectric' else robin.assemble_system(mesh,infos,pol,k)[0]
  else:a=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),leaf=max(16,leaf_size(coords)//spec.get('leaf_divisor',1)),budget=4*2**30)
  stage('assembly',t)
  if not dense:record['operator']=a.evidence
  t=time.perf_counter();b=dielectric.rhs_many(mesh,k,angles) if kind=='dielectric' else solver._robin_bie_rhs_many(mesh,oracle.alpha,oracle.pec_nodes,pol,k,angles);stage('rhs',t)
  diag={};t=time.perf_counter();fac=DenseFactor(a,diagnostics=diag,force_double=True,owned_matrix=True) if dense else HMatrixFactor(a,diagnostics=diag,storage_budget_bytes=4*2**30);stage('factor',t)
  if dense:assert fac.hierarchical is None and fac.mixed is None
  t=time.perf_counter();x=np.empty_like(b);width=spec.get('batch',180)
  for begin in range(0,180,width):x[:,begin:begin+width]=fac.solve(b[:,begin:begin+width])
  stage('solve',t)
  t=time.perf_counter();field=(op._farfield_linear_density_many(mesh,x[:n],k,angles,'DLP',projection='matched')+1j*k*op._farfield_linear_density_many(mesh,x[:n],k,angles,'SLP',projection='matched')) if kind=='dielectric' else op._farfield_linear_density_many(mesh,x,k,angles,'SLP',projection='matched');stage('field',t)
  record.update(compute_seconds=sum(record['stages'].values()),compute_peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20,diagnostics=diag,event=fac.event,pending_bytes=ledger.pending_construction_bytes)
  # Independent seed, excluding production's own sampled rows when possible.
  available=np.setdiff1d(np.arange(nd),getattr(a,'sample_rows',np.empty(0,int)))
  rows=np.sort(np.random.default_rng(2026111801).choice(available,min(64,len(available)),False))
  t=time.perf_counter();exact=exact_rows(oracle,rows,nd);residual=exact@x-b[rows];row_norm=np.sum(abs(exact),axis=1);x_norm=np.max(abs(x),axis=0)
  back=np.max(abs(residual)/(row_norm[:,None]*x_norm+abs(b[rows])))
  record.update(exact_backward_error=float(back),validation_seconds=time.perf_counter()-t,density_sha256=hashlib.sha256(x.tobytes()).hexdigest(),array_bytes=int(a.nbytes),matrix_layout=('F' if dense and a.flags.f_contiguous else 'C') if dense else None)
  assert np.isfinite(x).all() and np.isfinite(field).all() and np.isfinite(diag['condition_est']) and back<1e-12 and ledger.pending_construction_bytes==0
  arrays=dict(field=field,angles=angles,rows=rows,residual=residual,row_norm=row_norm,x_norm=x_norm,rhs_rows=b[rows])
  if spec.get('save_density'):arrays.update(density=x,rhs=b)
  np.savez_compressed(str(out)+'.npz',**arrays)
  if dense:fac.close()
except BaseException:
 record['error']=traceback.format_exc();print(record['error'],flush=True)
finally:
 record.update(wall_seconds=time.perf_counter()-start,peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20)
 out.with_suffix('.json').write_text(json.dumps(record,indent=2,default=str))
if record['error']:sys.exit(1)
