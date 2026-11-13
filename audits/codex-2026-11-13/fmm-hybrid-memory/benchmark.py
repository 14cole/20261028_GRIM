import os,sys,pathlib,json,time,resource,numpy as np
D=pathlib.Path(__file__).parent;ROOT=os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup');sys.path.insert(0,ROOT+'/tools/GHOST')
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
from ghost_backend.twod import operators as op
from fmm_galerkin import circle_mesh,GalerkinFMM
from cached_galerkin import CachedGalerkin
from hybrid_galerkin import HybridGalerkin
spec=json.loads(sys.argv[1]);out=pathlib.Path(spec['out']);n=spec['n'];k=complex(*spec.get('k',[40,0]));mode=spec['mode'];shape=spec.get('shape','star')
if shape in ['circle','star']:mesh=circle_mesh(n,star=shape=='star',inward=True)
else:
 # geometry_cases takes the repository path from argv[1] at import time.
 saved=sys.argv[1];sys.argv[1]=ROOT
 from geometry_cases import mesh_from_loops,circle,square
 sys.argv[1]=saved
 if shape=='gap':loops=[circle(n//2,1.,(-1.00005,0)),circle(n-n//2,1.,(1.00005,0))]
 elif shape=='coated':loops=[circle(n//2,1.),circle(n-n//2,.999)]
 elif shape=='graded':loops=[square(n//4,grade=3.)]
 else:raise ValueError(shape)
 mesh=mesh_from_loops(loops);n=len(mesh.nodes)
rng=np.random.default_rng(20261113);x=rng.normal(size=(n,2))+1j*rng.normal(size=(n,2));start=time.perf_counter();kinds=['S','K','KP','W']
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 if mode=='cached':g=CachedGalerkin(mesh,k)
 elif mode in ['native','native_tuned']:
  if mode=='native_tuned':
   import fmm_native_tuned,fmm_galerkin
   fmm_galerkin.evaluate=fmm_native_tuned.evaluate
  g=GalerkinFMM(mesh,k,eps=1e-12)
 else:g=HybridGalerkin(mesh,k,mode=mode,tol=spec.get('tol',1e-11),leaf=spec.get('leaf',24),eta=spec.get('eta',1.5),row_batch=spec.get('row_batch',64))
 if spec.get('require_compression'):assert g.near.compressed_pairs>0,'This qualification case must exercise low-rank storage'
 setup_wall=time.perf_counter()-start;rss_setup=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2;timings={};cpu_timings={};ys={}
 for kind in kinds:
  times=[];cpu_times=[]
  for _ in range(spec.get('warmups',0)):g.apply(x[:,0],kind)
  for _ in range(spec.get('repeats',3)):
   t=time.perf_counter();cpu=time.process_time();y=g.apply(x[:,0],kind);cpu_times.append(time.process_time()-cpu);times.append(time.perf_counter()-t)
  timings[kind]=times;cpu_timings[kind]=cpu_times;ys[kind]=g.apply(x,kind)
 rss_before_reference=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2
 ids=np.arange(n);rows=ids if spec.get('full',False) else np.unique(np.r_[rng.choice(n,min(16,n),replace=False),spec.get('check_rows',[])].astype(int));errors={};matrices={}
 for kind in kinds:
  if kind=='W':ref=op._assemble_linear_hypersingular_matrix(mesh,k,output_node_ids=(rows,ids)).values
  else:
   s,d=op._assemble_linear_operator_matrices_multi(mesh,k,kind=='KP',[None],compute_single_layer=kind=='S',compute_double_layer=kind!='S',output_node_ids_many=[(rows,ids)])[0];ref=(s if kind=='S' else d).values
  exact=ref@x;errors[kind]=dict(random_relative_max=float(np.max(abs(ys[kind][rows]-exact))/np.max(abs(exact))))
  arrays=dict(input=x,actual=ys[kind],reference_rows=ref,rows=rows,exact=exact)
  if spec.get('full',False):
   actual=np.concatenate([g.apply(np.eye(n,dtype=complex)[:,a:a+48],kind) for a in range(0,n,48)],axis=1);arrays['actual_matrix']=actual;errors[kind]['matrix_relative_max']=float(np.max(abs(actual-ref))/np.max(abs(ref)));errors[kind]['matrix_relative_fro']=float(np.linalg.norm(actual-ref)/np.linalg.norm(ref))
  if spec.get('check_rows'):
   selected=np.array(spec['check_rows']);entry_actual=g.apply(np.eye(n,dtype=complex)[:,selected],kind)[selected];entry_reference=ref[np.searchsorted(rows,selected)][:,selected];arrays.update(entry_indices=selected,entry_actual=entry_actual,entry_reference=entry_reference);errors[kind]['entry_max_absolute']=float(np.max(abs(entry_actual-entry_reference)))
  np.savez_compressed(str(out)+'-'+kind+'.npz',**arrays)
 stats=dict(spec,n=n,setup_seconds=setup_wall,near_seconds=getattr(g,'near_seconds',None),retained_bytes_partial=g.retained_bytes,near_bytes=getattr(g,'near_bytes',None),near_pairs=g.near_pairs,queried_pairs=getattr(g,'queried_pairs',None),kernel_seconds=getattr(g,'kernel_seconds',None),peak_setup_gib=rss_setup,peak_before_reference_gib=rss_before_reference,product_seconds=timings,product_cpu_seconds=cpu_timings,errors=errors,wall_seconds=time.perf_counter()-start,complete_solve=False,production_certified=False)
 if mode=='native_tuned':stats['native_profiles']=fmm_native_tuned.PROFILES
 if mode in ['hybrid','hybrid_nodal']:stats['hybrid']=dict(blocks=len(g.near.blocks),dense_pairs=g.near.dense_pairs,compressed_pairs=g.near.compressed_pairs,ranks=g.near.ranks,compression_rejections=g.near.failures,estimated_max_ratio=g.near.estimated_max_ratio)
 print(json.dumps(stats))
