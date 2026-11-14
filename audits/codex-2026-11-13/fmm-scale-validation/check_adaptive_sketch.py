"""Exercise paired row/column probes, oversized forecasts and exact errors."""
import os,sys,json,time
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST')
from ghost_backend.compressed import hmatrix as hm
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
from adaptive_sketch import adaptive_column_sketch
original=hm.cross_approximation;rng=np.random.default_rng(246);records=[];arrays={}
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 for label,m,n,rank,guess in [('overforecast',640,480,12,300),('underforecast',640,480,90,8),('large_overforecast',1200,1024,24,700)]:
  u=rng.normal(size=(m,rank))+1j*rng.normal(size=(m,rank));v=rng.normal(size=(rank,n))+1j*rng.normal(size=(rank,n));a=u@v
  # Two targets with different scales and one independent hidden rank direction.
  z=(rng.normal(size=(m,1))+1j*rng.normal(size=(m,1)))@(rng.normal(size=(1,n))+1j*rng.normal(size=(1,n)))
  z[hm._spread(min(m,max(8,int(1.25*guess)+16)),m)]=0
  targets=[a,1e-6*(a+1e-4*z)];tol=[1e-10*np.linalg.norm(x) for x in targets]
  for enabled,cap in [(False,None),(False,64),(True,None),(True,64)]:
   started=time.perf_counter()
   with adaptive_column_sketch(enabled,initial_rank_cap=cap) as stats:
    factors,estimated=hm.cross_approximation(lambda r:[x[r].copy() for x in targets],lambda c:[x[:,c].copy() for x in targets],(m,n),tol,guess,np.random.default_rng(129))
   assert hm.cross_approximation is original
   errors=[]
   for i,(target,(left,right),t) in enumerate(zip(targets,factors,tol)):
    error=float(np.linalg.norm(target-left@right));assert error<=4*t,(label,enabled,error/t);errors.append(error/t)
    arrays[f'{label}-{enabled}-{cap}-{i}-row_error']=np.linalg.norm(target-left@right,axis=1)
   records.append(dict(case=label,adaptive=enabled,initial_rank_cap=cap,ranks=[int(x[0].shape[1]) for x in factors],seconds=time.perf_counter()-started,full_error_to_tolerance=errors,estimated=estimated,evidence=stats))
  if label=='underforecast':assert all(x[0].shape[1]>64 for x in factors)
cap_only=[r for r in records if not r['adaptive'] and r['initial_rank_cap'] is not None]
assert any(r['evidence']['capped_calls'] for r in cap_only)
assert all(r['evidence']['reduced_selections']==0 for r in cap_only)
assert any(r['evidence']['reduced_selections'] for r in records if r['adaptive'] and r['initial_rank_cap'] is None)
np.savez_compressed('results/adaptive-sketch-contracts.npz',**arrays)
Path('results/adaptive-sketch-contracts.json').write_text(json.dumps(records,indent=2))
