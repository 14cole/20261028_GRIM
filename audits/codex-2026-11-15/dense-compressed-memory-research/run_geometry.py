"""Actual material/formulation path with unrelaxed discrete quality/condition gates."""
import os,sys,json,time,traceback,resource
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from hooks import install,RECORD,memory
from geometry_cases import build
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.execution.options import cpu_allocation_scope
from ghost_backend.twod import solver as S
from ghost_backend.linalg.dense import DenseFactor
from ghost_backend.compressed.factor import CompressedFactor
spec=json.loads(sys.argv[1]);install(spec);out=Path(spec['out']);captures=[];factors=[]
for cls in (DenseFactor,CompressedFactor):
    initial=cls.__init__;solve=cls.solve
    def init(self,*args,_fn=initial,**kwargs):
        try:return _fn(self,*args,**kwargs)
        finally:factors.append(getattr(self,'event',{}))
    def wrapped(self,b,_fn=solve):
        x=_fn(self,b);i=len(captures)
        np.savez_compressed(str(out)+f'-solve{i:04d}.npz',rhs=np.asarray(b),density=np.asarray(x))
        captures.append(dict(index=i,shape=list(np.shape(x))))
        return x
    cls.__init__=init;cls.solve=wrapped
text,geometry=build(spec);Path(str(out)+'.geo').write_text(text)
opts=dict(factorization=spec['method'],basis_order=1,mesh_strategy='global',
          assembly_threads=spec.get('threads',1),blas_threads=spec.get('threads',1),
          ram_budget_gib=10.,compressed_storage_mib=0,dense_residual_storage='memory',
          rhs_compression='off',angle_batch_size=spec.get('batch',256))
t=time.perf_counter();result=None;error=None;tb=None
try:
    g=build_geometry_snapshot(*parse_geometry(text))
    with cpu_allocation_scope(spec.get('threads',1)):
        result=S.solve_monostatic_rcs_2d_single_polarization(g,[spec['frequency_ghz']],
            np.linspace(-90,90,spec.get('count',180),endpoint=False).tolist(),spec.get('pol','TE'),
            geometry_units='meters',compute_condition_number=True,strict_quality_gate=True,
            max_panels=30000,execution_options=opts)
except Exception as exc:error=str(exc);tb=traceback.format_exc()
d=dict(spec=spec,geometry=geometry,wall_seconds=time.perf_counter()-t,error=error,traceback=tb,
       factors=factors,captures=captures,hooks=RECORD,**memory())
if result is not None:
    np.savez_compressed(str(out)+'-fields.npz',field=np.array([complex(s['rcs_amp_real'],s['rcs_amp_imag']) for s in result['samples']]))
    d['metadata']=result['metadata'];d['samples']=result['samples']
Path(str(out)+'.json').write_text(json.dumps(d,indent=2,default=str))
print(json.dumps(dict(case=out.name,error=error,wall=d['wall_seconds'],peak=d['peak_gib'])),flush=True)
if error:raise SystemExit(2)
