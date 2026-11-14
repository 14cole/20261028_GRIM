"""Compare complete near-block outputs across geometry and kernel regimes."""
import os,sys,json,time,runpy
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST')
sys.path.insert(0,str(Path(__file__).parent/'fmm'))
from ghost_backend.execution.cpu import CPUState,_STATE
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
from ghost_backend.twod import operators as op
from hybrid_galerkin import NearOracle
import native_pairs as native
argv=sys.argv;sys.argv=[str(Path(__file__).parent/'fmm/geometry_cases.py'),os.environ['GRIM_ROOT']]
geo=runpy.run_path(sys.argv[0]);sys.argv=argv
records=[];arrays={}
with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 for name,loops,k in [
  ('star-real',[geo['star'](192)],20.),('star-lossy',[geo['star'](192)],20.-.8j),
  ('star-strongloss',[geo['star'](192)],20.-8j),('star-low',[geo['star'](128)],.001),
  ('graded',[geo['square'](24,grade=3.)],10.),
  ('gap',[geo['circle'](96,1.,(-1.00005,0)),geo['circle'](96,1.,(1.00005,0))],10.-.1j),
  ('flat',[geo['ellipse'](192,2.,.1)],10.)]:
  mesh=geo['mesh_from_loops'](loops);n=len(mesh.elements);i=np.repeat(np.arange(n),n);j=np.tile(np.arange(n),n);oracle=NearOracle(mesh,k)
  for normal in [False,True]:
   # NearOracle uses source normals; normal=True separately calls classifier.
   g=oracle.g
   def run():
    out=[]
    for start in range(0,len(i),512):
     a,b=i[start:start+512],j[start:start+512]
     out.append(np.stack(op._near_pair_blocks(mesh.elements,a,b,k,normal,8,8,True,True,g.p0,g.segments,g.centers,g.lengths,g.node_ids,None,prepared_geometry=(g.p0,g.p0+g.segments,g.segments,g.lengths,g.normals))))
    return np.concatenate(out,axis=1)
   op._integrate_linear_pairs_box_sk_batched=native.original;t=time.perf_counter();ref=run();old=time.perf_counter()-t
   native.install();t=time.perf_counter();got=run();new=time.perf_counter()-t
   metrics=[]
   for c in range(2):
    absolute=float(abs(got[c]-ref[c]).max());relative=float(np.linalg.norm(got[c]-ref[c])/max(np.linalg.norm(ref[c]),1e-300));metrics.append(dict(absolute=absolute,relative=relative));assert relative<1e-11,(name,normal,metrics)
   key=name+'-'+str(normal);arrays[key+'_reference']=ref;arrays[key+'_native']=got
   records.append(dict(case=name,observer_normal=normal,old_seconds=old,new_seconds=new,metrics=metrics,stats=native.stats.copy()));print(name,normal,metrics,flush=True)
 # Operator flags, empty pairs and coincident tensor points.
 # Actual table fallback branches are exercised by check_native_fallbacks.py.
 mesh=geo['mesh_from_loops']([geo['star'](16)]);g=NearOracle(mesh,1.).g
 for sflag,kflag in [(True,False),(False,True)]:
  for ids in [np.array([],dtype=int),np.arange(16)]:
   args=(mesh.elements,ids,ids,1.,False,8,sflag,kflag)
   kw=dict(prepared_geometry=(g.p0,g.p0+g.segments,g.segments,g.lengths,g.normals))
   ref=native.original(*args,**kw);got=native.fixed(*args,**kw)
   for a,b in zip(ref,got):assert np.allclose(a,b,rtol=1e-12,atol=1e-14)
from pack_pair_arrays import pack
pack(Path('results/native-pair-validation.npz'),arrays)
Path('results/native-pair-validation.json').write_text(json.dumps(dict(checks=records,stats=native.stats),indent=2))
