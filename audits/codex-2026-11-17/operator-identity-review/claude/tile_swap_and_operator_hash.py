"""Reviewer checks: (1) swap assembly tile policy between 1 and 4 workers and hash exact rows;
(2) hash every retained array of the production HMatrix operator at 1 and 4 workers."""
import os,sys,json,hashlib
import numpy as np
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import (mesh_for,SimpleNamespace,NativeOracle,HMatrixOperator,support_radius,CPUState,_STATE,cpu_allocation_scope,execution_scope,exact_rows)
from ghost_backend.twod import operators as ops
rows=np.load(sys.argv[1])['rows'];n=4096;k=80.;eps=3-.08j;out={}
tile0=ops._assembly_tile_size
def scope(T):
    from contextlib import ExitStack
    s=ExitStack();s.enter_context(_STATE.override(CPUState(kernel_only=True)));s.enter_context(cpu_allocation_scope(T));s.enter_context(execution_scope({'assembly_threads':T,'blas_threads':1}));return s
def make():
    mesh=mesh_for(n,'star');info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
    return mesh,NativeOracle(mesh,[info],'TE',k,'dielectric')
def rows_hash(T,table=None,record=None):
    def tile(nelems,bpe,planned=True):
        key=f'{int(nelems)}|{int(bpe)}|{bool(planned)}'
        if table is not None:return table[key]
        v=tile0(nelems,bpe,planned)
        if record is not None:record[key]=int(v)
        return v
    ops._assembly_tile_size=tile
    try:
        with scope(T):
            mesh,oracle=make();e,_=exact_rows(oracle,rows,2*n)
    finally:ops._assembly_tile_size=tile0
    return hashlib.sha256(e.tobytes()).hexdigest()
t1={};t4={}
out['default_1_worker']=rows_hash(1,record=t1);out['default_4_workers']=rows_hash(4,record=t4)
out['tile_tables']={'1_worker':t1,'4_workers':t4}
out['1_worker_with_4_worker_tiles']=rows_hash(1,table=t4);out['4_workers_with_1_worker_tiles']=rows_hash(4,table=t1)
out['hash_follows_tile_policy']=bool(out['1_worker_with_4_worker_tiles']==out['default_4_workers'] and out['4_workers_with_1_worker_tiles']==out['default_1_worker'])
print(json.dumps({k_:v for k_,v in out.items()},indent=1),flush=True)
# (2) operator arrays
def operator_hashes(T):
    with scope(T):
        mesh,oracle=make();coords=np.tile(np.array([x.xy for x in mesh.nodes]),(2,1))
        h=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=12*2**30)
    seen=set();items=[];sizes=[]
    def walk(o,path):
        if id(o) in seen:return
        seen.add(id(o))
        if isinstance(o,np.ndarray):
            if o.dtype!=object:sizes.append(o.nbytes if o.base is None else 0);items.append((path,o.shape,str(o.dtype),hashlib.sha256(np.ascontiguousarray(o).tobytes()).hexdigest()))
            else:
                for i,x in enumerate(o.flat):walk(x,f'{path}[{i}]')
        elif isinstance(o,(list,tuple)):
            for i,x in enumerate(o):walk(x,f'{path}[{i}]')
        elif isinstance(o,dict):
            for key in sorted(o,key=str):walk(o[key],f'{path}.{key}')
        elif type(o).__module__.startswith('ghost_backend.compressed') and not callable(o):
            names=list(getattr(o,'__slots__',[]))+sorted(getattr(o,'__dict__',{}))
            for name in names:
                if name in ('oracle','checkpoint','ledger'):continue
                try:walk(getattr(o,name),f'{path}.{name}')
                except AttributeError:pass
    walk(h,'operator');coverage.append(int(sum(sizes)));return items,int(h.bytes),{k_:h.evidence.get(k_) for k_ in ('retained_bytes','near_bytes','far_bytes','max_rank','mean_rank','interaction_lists')}
coverage=[];a,ba,ea=operator_hashes(1);b,bb,eb=operator_hashes(4)
da={p:(s,d,hh) for p,s,d,hh in a};db={p:(s,d,hh) for p,s,d,hh in b}
diff=[p for p in sorted(set(da)|set(db)) if da.get(p)!=db.get(p)]
complex_paths=[p for p in da if da[p][1].startswith('complex')]
out['operator']=dict(arrays_1_worker=len(a),arrays_4_workers=len(b),same_array_paths=set(da)==set(db),differing_arrays=len(diff),differing_examples=diff[:10],
    complex_arrays=len(complex_paths),hashed_owned_array_bytes=coverage,complex_arrays_differing=sum(1 for p in diff if p in complex_paths),bytes=(ba,bb),evidence_1=ea,evidence_4=eb,
    combined_sha256_1=hashlib.sha256(json.dumps(sorted(da.items())).encode()).hexdigest(),combined_sha256_4=hashlib.sha256(json.dumps(sorted(db.items())).encode()).hexdigest())
print(json.dumps(out['operator'],indent=1));json.dump(out,open(sys.argv[2],'w'),indent=1)
