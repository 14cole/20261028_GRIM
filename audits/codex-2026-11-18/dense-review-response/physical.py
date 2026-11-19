"""Instrument the real public geometry solve, leaving all release gates on."""
import os,sys,pathlib,json,time,hashlib,resource,traceback
import numpy as np
spec=json.loads(sys.argv[1]);sys.path.insert(0,str(pathlib.Path(spec['root'])/'tools/GHOST'))
from geometry_cases import build
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.execution.options import cpu_allocation_scope
from ghost_backend.execution.thread_control import threadpool_info
from ghost_backend.twod import solver
from ghost_backend.linalg.dense import DenseFactor
text,geometry=build(spec);snapshot=build_geometry_snapshot(*parse_geometry(text));out=pathlib.Path(spec['out']);out.parent.mkdir(parents=True,exist_ok=True)
calls=[];captures={};source=pathlib.Path(sys.modules[DenseFactor.__module__].__file__).read_bytes()
original=DenseFactor.solve
def measured(self,b):
 t=time.perf_counter();x=original(self,b);elapsed=time.perf_counter()-t
 calls.append(dict(seconds=elapsed,width=int(np.shape(b)[1]),condition=(self.diagnostics or {}).get('condition_est'),physical=self.event['max_backward_error'],scaled=self.event['max_equilibrated_backward_error'],pools=threadpool_info()))
 if len(calls)==1:captures.update(rhs=np.array(b[:,:16]),density=np.array(x[:,:16]))
 return x
DenseFactor.solve=measured
error=None;t=time.perf_counter();result=None
try:
 options=dict(factorization='dense',basis_order=1,mesh_strategy='global',assembly_threads=spec['threads'],blas_threads=spec['threads'],ram_budget_gib=8,compressed_storage_mib=0,dense_residual_storage='memory',rhs_compression='off',angle_batch_size=spec['batch'])
 with cpu_allocation_scope(spec['threads']):
  result=solver.solve_monostatic_rcs_2d_single_polarization(snapshot,[spec['frequency_ghz']],np.linspace(-90,90,180,endpoint=False).tolist(),spec.get('pol','TE'),geometry_units='meters',compute_condition_number=True,strict_quality_gate=True,max_panels=30000,execution_options=options)
except BaseException:error=traceback.format_exc()
record=dict(spec=spec,geometry=geometry,error=error,wall_seconds=time.perf_counter()-t,solve_seconds=sum(x['seconds'] for x in calls),calls=calls,peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20,source_blob=hashlib.sha1(b'blob '+str(len(source)).encode()+b'\0'+source).hexdigest())
if result is not None:
 captures.update(field=np.array([complex(s['rcs_amp_real'],s['rcs_amp_imag']) for s in result['samples']]))
 record['metadata']=result['metadata'];np.savez_compressed(out.with_suffix('.npz'),**captures)
out.with_suffix('.json').write_text(json.dumps(record,indent=2,default=str));print(out.name,error,record['solve_seconds'],flush=True)
if error:sys.exit(1)
