import sys,os,json,time,pathlib,resource,numpy as np
D=pathlib.Path(__file__).parent;sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup')+'/tools/GHOST')
from ghost_backend.twod import operators as op
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
from fmm_galerkin import GalerkinFMM,circle_mesh
from cached_galerkin import CachedGalerkin
spec=json.loads(sys.argv[1]);n=spec['n'];k=complex(*spec['k']);mesh=circle_mesh(n,radius=spec.get('radius',1.),star=True,inward=True);rng=np.random.default_rng(20261113);x=rng.normal(size=n)+1j*rng.normal(size=n);rows=np.sort(rng.choice(n,16,replace=False));cols=np.arange(n);results=[]
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 a=CachedGalerkin(mesh,k) if spec['engine']=='cached' else GalerkinFMM(mesh,k,eps=1e-12);peak_setup=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2;ys={}
 for kind in spec.get('operators',['S','K','KP','W']):
  timings=[]
  for _ in range(spec.get('repeats',2)):
   start=time.perf_counter();y=a.apply(x,kind);timings.append(time.perf_counter()-start)
  ys[kind]=y;np.save(spec['out']+'-'+kind+'.npy',y);results.append(dict(operator=kind,product_seconds=timings,peak_before_reference_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2))
 for result in results:
  kind=result['operator']
  if kind=='W':ref=op._assemble_linear_hypersingular_matrix(mesh,k,output_node_ids=(rows,cols)).values@x
  else:
   s,d=op._assemble_linear_operator_matrices_multi(mesh,k,kind=='KP',[None],compute_single_layer=kind=='S',compute_double_layer=kind!='S',output_node_ids_many=[(rows,cols)])[0];ref=(s if kind=='S' else d).values@x
  result['relative_error']=float(np.max(abs(ys[kind][rows]-ref))/np.max(abs(ref)));np.save(spec['out']+'-'+kind+'-exact.npy',ref)
print(json.dumps(dict(spec,setup_seconds=a.setup_seconds,near_seconds=getattr(a,'near_seconds',None),retained_bytes_partial=a.retained_bytes,near_panel_pairs=a.near_pairs,peak_setup_gib=peak_setup,results=results,checked_rows=rows.tolist(),complete_solve=False)))
