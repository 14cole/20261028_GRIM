"""Parameter check on complete saved columns containing the original worst entries."""
import pathlib,sys,json,numpy as np
from geometry_cases import CASES,mesh_from_loops,op,cpu_allocation_scope,execution_scope,CachedGalerkin
D=pathlib.Path(__file__).parent;out=[]
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 for name in ['level-transition-3-4b','square-graded']:
  build,k=CASES[name];mesh=mesh_from_loops(build());n=len(mesh.nodes)
  for digits,separation in [(8,2),(10,3)]:
   f=CachedGalerkin(mesh,k,digits=digits,separation=separation);errors={}
   for kind in ['S','K','KP','W']:
    raw=np.load(D/(name+'-'+kind+'.npz'));columns=raw['columns'];x=np.zeros((n,len(columns)),complex);x[columns,np.arange(len(columns))]=1;actual=f.apply(x,kind);ref=raw['reference_columns'];errors[kind]=float(np.max(abs(actual-ref))/np.max(abs(ref)));np.savez_compressed(D/(name+f'-d{digits}-s{separation}-'+kind+'.npz'),columns=columns,actual=actual,reference=ref)
   out.append(dict(case=name,digits=digits,separation=separation,checked='complete columns containing 20 baseline worst entries per operator; not full matrix',setup_seconds=f.setup_seconds,near_pairs=f.near_pairs,errors=errors))
(D/'ACCURACY_DIAGNOSTIC.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
