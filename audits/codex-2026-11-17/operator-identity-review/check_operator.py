"""Two fresh production operator builds, payload manifests and query allocation traces."""
import os,sys,json,hashlib,gc,threading
from pathlib import Path
from collections import Counter
import numpy as np
from threadpoolctl import threadpool_limits,threadpool_info
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import mesh_for,SimpleNamespace,NativeOracle,HMatrixOperator,support_radius,CPUState,_STATE,cpu_allocation_scope,execution_scope,op
R=Path(__file__).resolve().parent;D=R/'results';D.mkdir(exist_ok=True)
if (D/'operators.json').exists():raise RuntimeError('Refusing overwrite')
sha=lambda a:hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
get0=NativeOracle.get_with_error;tile0=op._assembly_tile_size
def manifest(operator):
    seen=set();entries=[];owners={}
    def visit(obj,path):
        if id(obj) in seen:return
        seen.add(id(obj))
        if isinstance(obj,np.ndarray):
            if obj.dtype.hasobject:
                for i,value in enumerate(obj.flat):visit(value,path+'['+str(i)+']')
            else:
                entries.append(dict(path=path,shape=list(obj.shape),dtype=str(obj.dtype),strides=list(obj.strides),sha256=sha(obj),nbytes=obj.nbytes,owns_data=obj.base is None))
                owner=obj
                while isinstance(owner.base,np.ndarray):owner=owner.base
                owners[id(owner)]=owner.nbytes
        elif isinstance(obj,(list,tuple)):
            for i,value in enumerate(obj):visit(value,path+'['+str(i)+']')
        elif isinstance(obj,dict):
            for key in sorted(obj,key=str):visit(obj[key],path+'.'+str(key))
        elif type(obj).__module__.startswith('ghost_backend.compressed') and not callable(obj):
            slots=[]
            for cls in type(obj).__mro__:
                s=getattr(cls,'__slots__',());slots.extend([s] if isinstance(s,str) else s)
            for name in slots+sorted(getattr(obj,'__dict__',{})):
                if name in ('oracle','checkpoint','ledger'):continue
                if hasattr(obj,name):visit(getattr(obj,name),path+'.'+name)
    visit(operator,'operator')
    payload={e['path']:(e['shape'],e['dtype'],e['sha256']) for e in entries}
    return dict(arrays=entries,array_count=len(entries),complex_count=sum(e['dtype'].startswith('complex') for e in entries),
        directly_owned_bytes=sum(e['nbytes'] for e in entries if e['owns_data']),unique_numpy_owner_bytes=sum(owners.values()),
        combined_sha256=hashlib.sha256(json.dumps(sorted(payload.items())).encode()).hexdigest())
records=[]
for workers in (1,4):
    lock=threading.Lock();queries=Counter();tiles=Counter();worker_names=set()
    def get(self,rows,cols):
        effective=op.get_assembly_threads()
        with lock:queries[effective]+=1;worker_names.add(threading.current_thread().name)
        return get0(self,rows,cols)
    def tile(n,b,planned=True):
        value=tile0(n,b,planned)
        with lock:tiles[(n,b,planned,op.get_assembly_threads(),value)]+=1
        return value
    NativeOracle.get_with_error=get;op._assembly_tile_size=tile
    try:
      with threadpool_limits(limits=1,user_api='blas'),_STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(workers),execution_scope({'assembly_threads':workers,'blas_threads':1}):
        pools=[dict(prefix=p['prefix'],threads=p['num_threads'],version=p['version']) for p in threadpool_info() if p['user_api']=='blas']
        assert pools and all(p['threads']==1 for p in pools)
        mesh=mesh_for(4096,'star');k=80.;eps=3-.08j
        info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
        oracle=NativeOracle(mesh,[info],'TE',k,'dielectric');coords=np.tile(np.array([v.xy for v in mesh.nodes]),(2,1))
        h=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=12*2**30)
      data=manifest(h);data.update(workers=workers,operator_bytes=int(h.bytes),blas_pools=pools,
          effective_query_workers={str(k):v for k,v in sorted(queries.items())},query_worker_names=sorted(worker_names),
          tile_choices=[dict(elements=k[0],bytes_per_entry=k[1],planned=k[2],effective_workers=k[3],tile=k[4],calls=v) for k,v in sorted(tiles.items())],
          evidence={key:h.evidence[key] for key in ('retained_bytes','near_bytes','far_bytes','max_rank','mean_rank','interaction_lists')})
      assert data['directly_owned_bytes']==data['operator_bytes']==data['unique_numpy_owner_bytes']
      (D/('operator-'+str(workers)+'.json')).write_text(json.dumps(data,indent=2));records.append(data)
      print(json.dumps({k:v for k,v in data.items() if k not in ('arrays','tile_choices')}),flush=True)
      del h,oracle,mesh,coords;gc.collect()
    finally:NativeOracle.get_with_error=get0;op._assembly_tile_size=tile0
a,b=records
assert a['arrays']==b['arrays'] and a['combined_sha256']==b['combined_sha256']
out=dict(array_count=a['array_count'],complex_count=a['complex_count'],operator_bytes=a['operator_bytes'],combined_sha256=a['combined_sha256'],
         full_manifests_identical=True,workers=[1,4],new_solves=0,production_changes=0)
(D/'operators.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
