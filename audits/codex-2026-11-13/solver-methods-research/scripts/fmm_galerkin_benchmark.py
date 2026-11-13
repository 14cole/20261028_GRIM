"""Large P1 operator experiment, not a complete solve. Exact sampled rows."""
import pathlib,sys,os,json,time,resource,numpy as np
sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/grim-fmm-study')+'/tools/GHOST')
from ghost_backend.twod import operators as op
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
from fmm_galerkin import GalerkinFMM,circle_mesh
spec=json.loads(sys.argv[1]);n=spec['n'];k=2*np.pi*spec['ghz']*1e9/299792458.;mesh=circle_mesh(n,radius=3.048/1.2,star=True,inward=True);rng=np.random.default_rng(20261113);x=rng.normal(size=n)+1j*rng.normal(size=n);rows=np.sort(rng.choice(n,16,replace=False));cols=np.arange(n);results=[]
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 a=GalerkinFMM(mesh,k,eps=1e-12);setup_peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2
 values={}
 for kind in ['S','W']:
  start=time.perf_counter();y=a.apply(x,kind);elapsed=time.perf_counter()-start;apply_peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2;values[kind]=y
  np.save(spec['out']+'-'+kind+'.npy',y)
  results.append(dict(operator=kind,seconds=elapsed,apply_peak_rss_gib=apply_peak))
 for result in results:
  kind=result['operator'];y=values[kind]
  if kind=='S':matrix=op._assemble_linear_operator_matrices_multi(mesh,k,False,[None],compute_double_layer=False,output_node_ids_many=[(rows,cols)])[0][0]
  else:matrix=op._assemble_linear_hypersingular_matrix(mesh,k,output_node_ids=(rows,cols))
  exact=matrix.values@x;result['sampled_relative_max']=float(np.max(abs(y[rows]-exact))/np.max(abs(exact)));np.save(spec['out']+'-'+kind+'-sample.npy',exact)
print(json.dumps(dict(spec,setup_seconds=a.setup_seconds,setup_peak_rss_gib=setup_peak,retained_bytes_partial=a.retained_bytes,near_pairs=a.near_pairs,quadrature_points=len(a.points),dense_operator_gib=16*n*n/2**30,checked_rows=rows.tolist(),results=results,peak_including_validation_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2,complete_solve=False)))
