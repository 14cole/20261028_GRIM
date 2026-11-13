"""Paired old/new norm passes on identical physical compressed operators."""
import os,sys,json,time,runpy,types,resource
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST')
from ghost_backend.compressed.hmatrix import HMatrixOperator
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
from legacy_norms import LegacyNorms
spec=json.loads(sys.argv[1]);g=runpy.run_path('compressed_control.py',run_name='__main__');h=g['h']
new_abs=HMatrixOperator._absolute;new_norms=HMatrixOperator._norms
arrays={};times={'old':[],'new':[]};evidence={}
with cpu_allocation_scope(spec.get('threads',1)),execution_scope({'assembly_threads':spec.get('threads',1),'blas_threads':1}):
 for repeat in range(6):
  for version in (['old','new'] if repeat%2==0 else ['new','old']):
   h._absolute=types.MethodType(LegacyNorms._absolute if version=='old' else new_abs,h)
   fn=LegacyNorms._norms if version=='old' else new_norms
   start=time.perf_counter();fn(h);times[version].append(time.perf_counter()-start)
   for name in ['row_norm','row_max','column_norm','dimensionless_norms']:
    arrays[version+'_'+name]=np.asarray(getattr(h,name)).copy()
 for name in ['row_norm','row_max','column_norm','dimensionless_norms']:
  assert np.array_equal(arrays['old_'+name],arrays['new_'+name]),name
 h._absolute=types.MethodType(new_abs,h)
 # Optional dimensionless-only and scaled equilibration contracts stay exact.
 for scale in ([None,np.maximum(h.row_max[h.order],1e-20)] if h.n<8192 else []):
  for dimensionless in [False,True]:
   ref=LegacyNorms._absolute(h,scale,dimensionless);got=new_abs(h,scale,dimensionless)
   assert all(np.array_equal(a,b) for a,b in zip(ref,got))
np.savez_compressed(spec['out']+'-norms.npz',**arrays)
Path(spec['out']+'-norms.json').write_text(json.dumps(dict(spec,times=times,medians={k:float(np.median(v)) for k,v in times.items()},bitwise=True,fused_extra_partial_bytes=16*h.n+sum(8*(r.stop-r.start+len(r.columns)) for r in h.near+h.far+h.dense_far),peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20),indent=2))
