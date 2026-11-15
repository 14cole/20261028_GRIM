"""Fresh diagnostic: matched coordinates, adjoint norm iteration, leaf conditioning.
No full FMM sweep or timing comparison. No production or acceptance changes.
"""
import os,sys,json,time,gc
from pathlib import Path
import numpy as np
import scipy.linalg as la
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import (mesh_for,SimpleNamespace,NativeOracle,PreconditionerOperator,
 HMatrixOperator,HMatrixSystem,HMatrixFactor,support_radius,packed_operator_blocks,
 finish_operator,CPUState,_STATE,cpu_allocation_scope,execution_scope)
HERE=Path(__file__).resolve().parent
n=4096;k=80.;eps=3-.08j;mesh=mesh_for(n,'star')
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
coords=np.tile(np.array([x.xy for x in mesh.nodes]),(2,1))
def census(root):
    todo=[root];seen=set();out={}
    while todo:
        x=todo.pop()
        if id(x) in seen:continue
        seen.add(id(x))
        if isinstance(x,np.ndarray):
            e=out.setdefault(str(x.dtype),[0,0]);e[0]+=1;e[1]+=x.nbytes
        elif isinstance(x,(tuple,list)):todo.extend(x)
        elif isinstance(x,dict):todo.extend(x.values())
        elif hasattr(x,'__dict__'):todo.extend(vars(x).values())
    return out
def gain(forward,adjoint):
    rng=np.random.default_rng(151144)
    q=np.linalg.qr(rng.normal(size=(2*n,8))+1j*rng.normal(size=(2*n,8)))[0];history=[]
    for _ in range(20):
        z=forward(q);history.append(float(la.svdvals(z)[0]));q=np.linalg.qr(adjoint(z))[0]
    return history
def leaf_checks(root):
    out=[];todo=[root]
    while todo:
        node=todo.pop()
        if not node.leaf:todo.extend((node.left,node.right));continue
        lu,piv=node.lu;dim=len(lu);a=(np.tril(lu,-1)+np.eye(dim))@np.triu(lu)
        for i in range(dim-1,-1,-1):a[[i,piv[i]]]=a[[piv[i],i]]
        inv=la.lu_solve(node.lu,np.eye(dim,dtype=complex))
        out.append(float(la.norm(a,1)*la.norm(inv,1)))
    return dict(count=len(out),minimum=min(out),median=float(np.median(out)),maximum=max(out))
state=CPUState(kernel_only=True);results={}
with _STATE.override(state),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
    for kind in ('loose_fmm','production_compressed'):
        started=time.perf_counter();oracle=NativeOracle(mesh,[info],'TE',k,'dielectric')
        if kind=='loose_fmm':
            with packed_operator_blocks(True) as storage:h=PreconditionerOperator(oracle,coords,radius=support_radius(mesh,coords),tolerance=1e-4,budget=12*2**30)
            finish_operator(h,storage);rows,cols,_=h.equilibrate()
            inv=HMatrixSystem(h,coords,tolerance=1e-4,budget=12*2**30,checkpoint=None)
        else:
            h=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=12*2**30)
            f=HMatrixFactor(h,storage_budget_bytes=12*2**30);inv=f.factor;rows,cols,_=h.equilibrate()
        # Detach authoritative operator from census; retained inverse only.
        owner=inv.operator;inv.operator=None;counts=census(inv);inv.operator=owner
        forward=lambda x:cols[:,None]*inv.apply(rows[:,None]*x,solve=True)
        adjoint=lambda x:rows[:,None]*inv.apply(cols[:,None]*x,solve=True,trans=2)
        rng=np.random.default_rng(919);u=rng.normal(size=(2*n,4))+1j*rng.normal(size=(2*n,4));v=rng.normal(size=u.shape)+1j*rng.normal(size=u.shape)
        lhs=np.vdot(v,forward(u));rhs=np.vdot(adjoint(v),u)
        adjoint_error=float(abs(lhs-rhs)/max(abs(lhs),abs(rhs)))
        assert adjoint_error<1e-8
        scaled=gain(forward,adjoint)
        raw=gain(lambda x:inv.apply(x,solve=True),lambda x:inv.apply(x,solve=True,trans=2))
        result=dict(census=counts,leaf_condition_1=leaf_checks(inv.root),adjoint_inner_product_relative_error=adjoint_error,
          scaled_norm2_lower_bound_history=scaled,unscaled_norm2_lower_bound_history=raw,
          random_additivity_relative_error=float(la.norm(forward(u+v)-forward(u)-forward(v))/la.norm(forward(u+v))),seconds=time.perf_counter()-started)
        results[kind]=result;print(json.dumps({kind:result}),flush=True)
        (HERE/'inverse-diagnostic.json').write_text(json.dumps(results,indent=2))
        del forward,adjoint,owner,inv,h,oracle
        if kind!='loose_fmm':del f
        gc.collect()
