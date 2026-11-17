"""Reviewer check of Codex's explanation for operator identity across worker counts."""
import os,sys,json,hashlib
from collections import Counter
import numpy as np
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import (mesh_for,SimpleNamespace,NativeOracle,HMatrixOperator,support_radius,CPUState,_STATE,cpu_allocation_scope,execution_scope)
from ghost_backend.twod import operators as ops
n=4096;k=80.;eps=3-.08j;tile0=ops._assembly_tile_size;out={};ACTIONS=[]
def build(T,forced=None):
    calls=Counter()
    def tile(nelems,bpe,planned=True):
        v=tile0(nelems,bpe,planned)
        if forced and (int(nelems),int(bpe)) in forced:v=forced[(int(nelems),int(bpe))]
        calls[f'{int(nelems)}|{int(bpe)}|{int(v)}']+=1;return v
    ops._assembly_tile_size=tile
    try:
        with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(T),execution_scope({'assembly_threads':T,'blas_threads':1}):
            mesh=mesh_for(n,'star');info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
            coords=np.tile(np.array([x.xy for x in mesh.nodes]),(2,1));oracle=NativeOracle(mesh,[info],'TE',k,'dielectric')
            h=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=12*2**30)
            rng=np.random.default_rng(5);probe=rng.standard_normal((2*n,4))+1j*rng.standard_normal((2*n,4));action=h.matmul(probe)
    finally:ops._assembly_tile_size=tile0
    seen=set();arrays={}
    def walk(o,path):
        if id(o) in seen:return
        seen.add(id(o))
        if isinstance(o,np.ndarray):
            if o.dtype!=object:arrays[path]=o
            else:
                for i,x in enumerate(o.flat):walk(x,f'{path}[{i}]')
        elif isinstance(o,(list,tuple)):
            for i,x in enumerate(o):walk(x,f'{path}[{i}]')
        elif isinstance(o,dict):
            for key in sorted(o,key=str):walk(o[key],f'{path}.{key}')
        elif type(o).__module__.startswith('ghost_backend.compressed') and not callable(o):
            for name in list(getattr(o,'__slots__',[]))+sorted(getattr(o,'__dict__',{})):
                if name in ('oracle','checkpoint','ledger'):continue
                try:walk(getattr(o,name),f'{path}.{name}')
                except AttributeError:pass
    walk(h,'operator')
    hashes={p:(a.shape,str(a.dtype),hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()) for p,a in arrays.items()}
    ACTIONS.append(action);return dict(calls=dict(calls),combined=hashlib.sha256(json.dumps(sorted(hashes.items())).encode()).hexdigest(),evidence={k_:h.evidence.get(k_) for k_ in ('retained_bytes','max_rank','mean_rank')}),arrays,hashes
r1,a1,h1=build(1);r4,a4,h4=build(4);del a4
out['default_1_worker']=r1;out['default_4_workers']=r4
out['same_tile_decisions']=r1['calls']==r4['calls'];out['same_operator']=r1['combined']==r4['combined']
print('trace 1:',r1['calls']);print('trace 4:',r4['calls']);print('same decisions',out['same_tile_decisions'],'same operator',out['same_operator'],r1['combined'][:16],flush=True)
forced={(4096,184):256,(4096,296):256}
rf,af,hf=build(1,forced);out['forced_4_worker_direct_query_tiles_at_1_worker']=rf
diff=[p for p in h1 if h1[p]!=hf.get(p)];stats=[]
for p in diff:
    x,y=a1[p],af[p]
    if x.shape==y.shape and x.dtype==y.dtype:
        d=abs(x-y);stats.append(dict(path=p,dtype=str(x.dtype),entries=int(x.size),entries_differing=int((d>0).sum()),max_abs_diff=float(d.max()),max_abs_value=float(abs(x).max())))
    else:stats.append(dict(path=p,shape_or_dtype_changed=True,shapes=[list(x.shape),list(y.shape)]))
num=[s for s in stats if 'max_abs_diff' in s]
out['counterfactual']=dict(operator_changed=rf['combined']!=r1['combined'],same_array_paths=set(h1)==set(hf),arrays_total=len(h1),arrays_differing=len(diff),
    complex_differing=sum(1 for s in num if s['dtype'].startswith('complex')),noncomplex_differing=[s['path'] for s in stats if not str(s.get('dtype','')).startswith('complex')][:10],
    shape_changes=sum(1 for s in stats if s.get('shape_or_dtype_changed')),largest_abs_diff=max((s['max_abs_diff'] for s in num),default=0.),
    largest_relative_to_array_max=max((s['max_abs_diff']/s['max_abs_value'] for s in num if s['max_abs_value']>0),default=0.),
    entries_differing=sum(s['entries_differing'] for s in num),entries_in_differing_arrays=sum(s['entries'] for s in num),examples=stats[:6])
out['counterfactual']['operator_action_relative_difference']=float(np.linalg.norm(ACTIONS[2]-ACTIONS[0])/np.linalg.norm(ACTIONS[0]));out['counterfactual']['action_1_vs_4_workers_bitwise_equal']=bool(np.array_equal(ACTIONS[0],ACTIONS[1]))
near=[s_ for s_ in num if '.near' in s_['path']];far=[s_ for s_ in num if '.far' in s_['path']]
out['counterfactual']['near_arrays_differing']=len(near);out['counterfactual']['near_largest_abs_diff']=max((s_['max_abs_diff'] for s_ in near),default=0.);out['counterfactual']['far_arrays_differing']=len(far);out['counterfactual']['far_largest_abs_diff']=max((s_['max_abs_diff'] for s_ in far),default=0.);out['counterfactual']['all_differing_paths']=[s_['path'] for s_ in stats]
print('forced trace:',rf['calls']);print(json.dumps(out['counterfactual'],indent=1))
json.dump(out,open(sys.argv[1],'w'),indent=1)
