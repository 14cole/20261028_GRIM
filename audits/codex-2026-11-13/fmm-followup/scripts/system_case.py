"""Complete discrete PEC/TE/TM solves; research, no mesh/production certificate.
Dense reference and banded ILU extracted from it intentionally remain live.
This measures convergence/correctness, NOT FMM-only process capacity.
"""
import sys,os,json,time,pathlib,resource
import numpy as np
from scipy.linalg import lu_factor,lu_solve
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import LinearOperator,gmres,spilu
sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup')+'/tools/GHOST')
from ghost_backend.twod import operators as op
from ghost_backend.twod.formulations import dielectric
from ghost_backend.twod.assembly.mass import sparse_mass
from ghost_backend.linalg.workspace import equilibrated_scaling_and_norm_1
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
from fmm_galerkin import GalerkinFMM as NativeGalerkin,circle_mesh
from cached_galerkin import CachedGalerkin
from scipy.sparse import bmat,diags
def GalerkinFMM(mesh,k,**kwargs):
 return NativeGalerkin(mesh,k,**kwargs) if spec.get("engine")=="native" else CachedGalerkin(mesh,k)
from types import SimpleNamespace
spec=json.loads(sys.argv[1]);n=spec['n'];k0=spec['k'];kind=spec['kind'];epsr=complex(3.,-.08);k1=k0*np.sqrt(epsr);mesh=circle_mesh(n,star=spec.get('star',False),inward=True);angles=np.array(spec.get('incident_angles',[0.,47.,121.] if kind=='TE' or not spec.get('star',False) else [0.]));max_cycles=spec.get('gmres_max_cycles',6 if kind=='TE' or not spec.get('star',False) else 2);obs=np.arange(0.,360.,2.)
started=time.perf_counter()
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 mass=sparse_mass(mesh);ex=GalerkinFMM(mesh,k0,eps=1e-13)
 if kind=='PEC':
  s,d=op._assemble_linear_operator_matrices(mesh,k0,False);a=.5*mass.toarray()+d+1j*k0*s;b=dielectric.rhs_many(mesh,k0,angles)[:n];inter=None
  def apply(x):return .5*(mass@x)+ex.apply(x,'K')+1j*k0*ex.apply(x,'S')
 else:
  inter=GalerkinFMM(mesh,k1,eps=1e-13);factor=1/epsr if kind=='TE' else 1.
  infos=[SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=epsr,k_plus=k1,k_minus=k0,plus_region=1,minus_region=0)]
  a=dielectric.assemble_system(mesh,infos,kind,k0);b=dielectric.rhs_many(mesh,k0,angles)
  def apply(x):
   u,v=x[:n],x[n:];top=.5*(mass@u)+ex.apply(u,'K')+1j*k0*ex.apply(u,'S')-inter.apply(v,'S')
   bottom=ex.apply(u,'W')-1j*k0*ex.apply(u,'KP')+.5j*k0*(mass@u)+factor*(inter.apply(v,'KP')+.5*(mass@v))
   return np.concatenate((top,bottom))
 rows,cols,norma=equilibrated_scaling_and_norm_1(a);scaled=a/rows[:,None]/cols[None,:];nd=len(a)
 rng=np.random.default_rng(123);q=rng.normal(size=(nd,2))+1j*rng.normal(size=(nd,2));actual=apply(q);truth=a@q
 operator_error=float(np.max(abs(actual-truth))/np.max(abs(truth)))
 def scaled_apply(y):return apply(y/cols)/rows
 lin=LinearOperator((nd,nd),matvec=scaled_apply,dtype=complex)
 t=time.perf_counter();lu,piv=lu_factor(scaled);reference=lu_solve((lu,piv),b/rows[:,None])/cols[:,None];dense_solve_seconds=time.perf_counter()-t
 def farfield(x):return op._farfield_linear_density_many(mesh,x[:n],k0,obs,'DLP',projection='grid')+1j*k0*op._farfield_linear_density_many(mesh,x[:n],k0,obs,'SLP',projection='grid')
 ref_field=farfield(reference);analytic=None;analytic_sigma=None
 if kind in ['TE','TM'] and not spec.get('star',False):
  from ghost_backend.validation.cylinder import sigma_dielectric_cylinder
  analytic_sigma=sigma_dielectric_cylinder(1.,epsr,1.,k0*299792458./(2*np.pi),kind)
 if kind=='PEC' and not spec.get('star',False):
  from ghost_backend.validation.cylinder import pec_cylinder_backscatter_amplitude
  analytic=pec_cylinder_backscatter_amplitude(1.,k0*299792458./(2*np.pi),'TM')
 out=pathlib.Path(spec['out']);np.save(str(out)+'-reference.npy',ref_field);np.save(str(out)+'-reference-density.npy',reference)
 results=[]
 for precond in spec.get('preconditioners',['none','near_ilu','fmm_near_ilu']):
  prestart=time.perf_counter();prebytes=0
  if precond=='near_ilu':
   ids=np.arange(nd)%n;delta=abs(ids[:,None]-ids[None,:]);mask=np.minimum(delta,n-delta)<=8;near=csc_matrix(np.where(mask,scaled,0));ilu=spilu(near,drop_tol=1e-5,fill_factor=10);pre=LinearOperator((nd,nd),matvec=ilu.solve,dtype=complex);prebytes=sum(z.data.nbytes+z.indices.nbytes+z.indptr.nbytes for z in [ilu.L,ilu.U])
  elif precond=='fmm_near_ilu':
   c=ex.corrections
   if kind=='PEC':near=.5*mass+c['K']+1j*k0*c['S']
   else:
    d=inter.corrections
    near=bmat([[.5*mass+c['K']+1j*k0*c['S'],-d['S']],[c['W']-1j*k0*c['KP']+.5j*k0*mass,factor*(d['KP']+.5*mass)]],format='csc')
   near=diags(1/rows)@near@diags(1/cols);ilu=spilu(near.tocsc(),drop_tol=1e-3,fill_factor=5);pre=LinearOperator((nd,nd),matvec=ilu.solve,dtype=complex);prebytes=sum(z.data.nbytes+z.indices.nbytes+z.indptr.nbytes for z in [ilu.L,ilu.U])
  elif precond=='full_lu_control':pre=LinearOperator((nd,nd),matvec=lambda x:lu_solve((lu,piv),x),dtype=complex);prebytes=lu.nbytes+piv.nbytes
  else:pre=None
  setup=time.perf_counter()-prestart;solutions=[];iterations=[];statuses=[];t=time.perf_counter()
  for col in range(b.shape[1]):
   history=[];y,info=gmres(lin,b[:,col]/rows,M=pre,rtol=1e-12,atol=0,restart=80,maxiter=max_cycles,callback=lambda v:history.append(float(v)),callback_type='pr_norm');solutions.append(y/cols);iterations.append(len(history));statuses.append(int(info))
  elapsed=time.perf_counter()-t;x=np.column_stack(solutions);res=a@x-b;physical=float(np.max(np.max(abs(res),axis=0)/(np.linalg.norm(a,np.inf)*np.max(abs(x),axis=0)+np.max(abs(b),axis=0))));scaled_error=float(np.max(np.sum(abs(res)/rows[:,None],axis=0)/(norma*np.sum(abs(x)*cols[:,None],axis=0)+np.sum(abs(b)/rows[:,None],axis=0))))
  field=farfield(x);field_error=float(np.max(abs(field-ref_field))/np.max(abs(ref_field)));np.save(str(out)+'-'+precond+'.npy',field);np.save(str(out)+'-'+precond+'-density.npy',x)
  results.append(dict(preconditioner=precond,preconditioner_bytes=prebytes,preconditioner_setup_seconds=setup,solve_seconds=elapsed,iterations=iterations,statuses=statuses,physical_backward_error=physical,scaled_backward_error=scaled_error,field_relative_max_error=field_error,analytic_backscatter_relative_error=float(abs(field[0,0]-analytic)/abs(analytic)) if analytic is not None else None,analytic_sigma_relative_error=float(abs(abs(field[0,0])**2/(4*k0)-analytic_sigma)/analytic_sigma) if analytic_sigma is not None else None,linear_checks_passed=all(i==0 for i in statuses) and max(physical,scaled_error)<=1e-12))
 result=dict(spec,preconditioner_scales_from_dense_reference=True,incident_angles=angles.tolist(),gmres_restart=80,gmres_max_cycles=max_cycles,operator_relative_max_error=operator_error,dense_reference_solve_seconds=dense_solve_seconds,operator_setup_seconds=ex.setup_seconds+(inter.setup_seconds if inter else 0),operator_retained_bytes_partial=ex.retained_bytes+(inter.retained_bytes if inter else 0),fmm_calls=ex.calls+(inter.calls if inter else 0),condition_1_scaled=float(abs(np.linalg.cond(scaled,1))),results=results,wall_seconds=time.perf_counter()-started,peak_rss_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2,dense_validation_live=True,production_certified=False)
 print(json.dumps(result))
