"""Independent checks of Claude's review; production files remain unchanged."""
import json,sys,time,threading
from pathlib import Path
import numpy as np,psutil
root=Path(sys.argv[1]).resolve();case=sys.argv[2];out=Path(sys.argv[3]).resolve()
sys.path.insert(0,str(root/'tools/GHOST'))
from ghost_backend.twod import solver as S
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
from ghost_backend.execution.policy import rank_automatic

def find(x,key):
 if isinstance(x,dict):
  if key in x:yield x[key]
  for v in x.values():yield from find(v,key)
 elif isinstance(x,list):
  for v in x:yield from find(v,key)

if case=='policy':
 rows=[]
 candidates={'dense':dict(peak_gb=.5,cost=.01),'compressed':dict(peak_gb=.5,cost=100.)}
 for n,peaks,wanted in [(9999,(.5,.5),'dense'),(10000,(.5,.5),'compressed'),(14000,(.5,2.),'dense'),(8000,(2.,.5),'compressed'),(8000,(.9,.5),'compressed')]:
  c={k:dict(v,peak_gb=peaks[i]) for i,(k,v) in enumerate(candidates.items())};diagnostics={}
  order=rank_automatic(c,1.,n,diagnostics=diagnostics);assert order[0]==wanted
  rows.append(dict(unknowns=n,peaks=peaks,order=order,diagnostics=diagnostics))
 (out/'policy.json').write_text(json.dumps(rows,indent=2)+'\n');print('PASS policy: five boundary/admission examples');sys.exit(0)

if case.startswith('airfoil'):
 geometry=build_geometry_snapshot(*parse_geometry((root/'airfoil.geo').read_text()))
 frequencies=[1.5,3.];units='inches';reference=1.
 opts=dict(factorization='dense',mesh_strategy='adaptive',assembly_threads=4,blas_threads=4)
 if case.endswith('1g'):opts['ram_budget_gib']=1.
 certified=True;angles=list(np.linspace(0,180,181))
elif case.startswith('fixed'):
 square=[(0,0),(0,1),(1,1),(1,0),(0,0)]
 xy='\n'.join('%g %g %g %g'%(*square[i],*square[i+1]) for i in range(4))
 geometry=build_geometry_snapshot(*parse_geometry('Title: fixed\nSegment: b 2\nproperties: 2 5 0 0 0\n'+xy+'\nIBCS_Resistances:\nDielectrics:\n'))
 frequencies=[.3,1.5];units='meters';reference=.3;angles=[0.,30.,45.]
 opts=dict(factorization='dense',mesh_strategy='global',enforce_mesh_density=False,assembly_threads=1,blas_threads=1)
 certified=case.endswith('certified')
else:raise ValueError(case)

estimates=[];original=S._estimate_memory_gb
def observe(*args,**kwargs):
 value=original(*args,**kwargs)
 if kwargs.get('activate_memory_plan'):
  estimates.append(dict(estimate_gib=value,plan=json.loads(json.dumps(kwargs.get('dense_resources',{}).get('memory_estimate',{})))))
 return value
S._estimate_memory_gb=observe
process=psutil.Process();rss=[];done=threading.Event()
def sampler():
 while not done.is_set():rss.append(process.memory_info().rss);done.wait(.01)
thread=threading.Thread(target=sampler);thread.start();started=time.perf_counter();error=None;result=None
try:
 with cpu_allocation_scope(4):
  fn=S.solve_monostatic_rcs_2d_certified if certified else S.solve_monostatic_rcs_2d_survey
  result=fn(geometry,frequencies,angles,geometry_units=units,mesh_reference_ghz=reference,execution_options=opts,max_panels=200000)
except Exception as exc:error=type(exc).__name__+': '+str(exc)
finally:done.set();thread.join()
record=dict(case=case,seconds=time.perf_counter()-started,peak_rss_gib=max(rss)/2**30,error=error,estimates=estimates,options=opts,frequencies=frequencies,reference=reference)
if result is not None:
 meta=result['metadata'];q=meta['quadrature_qualification'];record.update(certified=meta['mesh_convergence_certified'],qualification=q,panels=meta['panel_count'],quality=meta['quality_gate'],storage_records=list(find(meta,'residual_storage')))
 fields=np.array([complex(v['rcs_amp_real'],v['rcs_amp_imag']) for v in result['samples']]);record['samples']=len(fields)
 np.savez(out/(case+'.npz'),field=fields)
 (out/(case+'.metadata.json')).write_text(json.dumps(meta,default=str))
 if case.startswith('airfoil'):
  assert record['certified'] and all(v['qualified'] for v in q),record
  assert set(v['frequency_ghz'] for v in q)=={1.5,3.}
  assert len(fields)==724 and meta['quality_gate']['passed']
  if case.endswith('1g'):assert 'disk' in record['storage_records']
 else:
  assert not record['certified'] and meta['quality_gate']['passed']
  assert all(v['qualified']==(v['frequency_ghz']==.3) for v in q)
if case=='fixed-certified':assert error and 'quadrature is not qualified on the base mesh' in error,error
else:assert result is not None,error
(out/(case+'.json')).write_text(json.dumps(record,indent=2)+'\n')
print(case,round(record['seconds'],2),round(record['peak_rss_gib'],3),error or 'PASS',flush=True)
