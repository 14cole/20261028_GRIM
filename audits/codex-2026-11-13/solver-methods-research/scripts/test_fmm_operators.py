import pathlib,sys,json,time,resource,os
import numpy as np
sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/grim-fmm-study')+'/tools/GHOST')
from ghost_backend.twod import operators as op
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
from fmm_galerkin import GalerkinFMM,circle_mesh
results=[]
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 for n,k,star in [(64,3.,False),(128,12.-.2j,False),(256,20.,True)]:
  mesh=circle_mesh(n,star=star);a=GalerkinFMM(mesh,k);rng=np.random.default_rng(123);x=rng.normal(size=(n,3))+1j*rng.normal(size=(n,3))
  s,kp=op._assemble_linear_operator_matrices(mesh,k,True);_,kk=op._assemble_linear_operator_matrices(mesh,k,False,compute_single_layer=False);w=op._assemble_linear_hypersingular_matrix(mesh,k)
  for kind,matrix in [('S',s),('K',kk),('KP',kp),('W',w)]:
   start=time.perf_counter();y=a.apply(x,kind);elapsed=time.perf_counter()-start;truth=matrix@x;err=float(np.max(abs(y-truth))/np.max(abs(truth)));print(n,k,kind,err,elapsed,flush=True);results.append(dict(n=n,k=[complex(k).real,complex(k).imag],star=star,operator=kind,error=err,seconds=elapsed,setup_seconds=a.setup_seconds,retained_bytes=a.retained_bytes))
pathlib.Path(__file__).with_name('FMM_OPERATOR_CHECKS.json').write_text(json.dumps(results,indent=2)+'\n')
assert max(r['error'] for r in results)<1e-9
