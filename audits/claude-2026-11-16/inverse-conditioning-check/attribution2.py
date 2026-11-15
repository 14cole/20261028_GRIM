"""Reviewer diagnostic: component-level error attribution for the retained
HODLR inverse apply, using extended precision for selected components."""
import os,sys,json,time
from pathlib import Path
import numpy as np,scipy.linalg as la
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import (mesh_for,SimpleNamespace,NativeOracle,PreconditionerOperator,HMatrixSystem,support_radius,
 packed_operator_blocks,finish_operator,CPUState,_STATE,cpu_allocation_scope,execution_scope)
LD=np.clongdouble
n=4096;k=80.;eps=3-.08j;mesh=mesh_for(n,'star');N=2*n
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
coords=np.tile(np.array([x.xy for x in mesh.nodes]),(2,1));out={'longdouble_eps':float(np.finfo(np.longdouble).eps)}
def rebuild(lu):
    f,piv=lu;m=len(f);a=(np.tril(f,-1)+np.eye(m)).astype(LD)@np.triu(f).astype(LD)
    for i in range(m-1,-1,-1):a[[i,piv[i]]]=a[[piv[i],i]]
    return a
def refined(lu,a,b,steps=3):
    x=la.lu_solve(lu,np.asarray(b,complex),check_finite=False).astype(LD);b=b.astype(LD)
    for _ in range(steps):x=x+la.lu_solve(lu,np.asarray(b-a@x,complex),check_finite=False).astype(LD)
    return x
def apply(node,b,mode):
    # mode: set of components done in extended precision: 'leaf','small','prod'
    if node.leaf:
        if 'leafscaled' in mode:return la.lu_solve(node._slu,np.asarray(b,complex)*node._dr[:,None],check_finite=False).astype(b.dtype)
        if 'leafscaled2' in mode:return (node._dc[:,None]*la.lu_solve(node._slu2,np.asarray(b,complex)*node._dr2[:,None],check_finite=False)).astype(b.dtype)
        return refined(node.lu,node._a,b) if 'leaf' in mode else la.lu_solve(node.lu,np.asarray(b,complex),check_finite=False).astype(b.dtype)
    m=node.left.n;z1=apply(node.left,b[:m],mode);z2=apply(node.right,b[m:],mode)
    if node.lu is None:return np.vstack((z1,z2))
    P='prod' in mode
    def mul(a,x):return a.astype(LD)@x.astype(LD) if P else (np.asarray(a,complex)@np.asarray(x,complex))
    small=np.vstack((mul(node.v12,z2),mul(node.v21,z1)))
    c=refined(node.lu,node._a,small) if 'small' in mode else la.lu_solve(node.lu,np.asarray(small,complex),check_finite=False)
    r=node.e1.shape[1];d1=mul(node.e1,c[:r]);d2=mul(node.e2,c[r:])
    if mode-{'leafscaled','leafscaled2'}:return np.vstack((z1.astype(LD)-d1,z2.astype(LD)-d2))
    return np.vstack((z1-d1,z2-d2))
def nodes(root):
    todo=[root]
    while todo:
        x=todo.pop();yield x
        if not x.leaf:todo.extend((x.left,x.right))
def gain(forward,adjoint,its=30):
    r=np.random.default_rng(31);q=np.linalg.qr(r.standard_normal((N,8))+1j*r.standard_normal((N,8)))[0];h=[]
    for _ in range(its):
        z=forward(q);h.append(float(la.svdvals(z)[0]));q=np.linalg.qr(adjoint(z))[0]
    return h
state=CPUState(kernel_only=True)
with _STATE.override(state),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
    oracle=NativeOracle(mesh,[info],'TE',k,'dielectric')
    with packed_operator_blocks(True) as storage:h=PreconditionerOperator(oracle,coords,radius=support_radius(mesh,coords),tolerance=1e-4,budget=12*2**30)
    finish_operator(h,storage);rows,cols,_=h.equilibrate()
    inv=HMatrixSystem(h,coords,tolerance=1e-4,budget=12*2**30,checkpoint=None)
    perm=inv.permutation;out['row_scale_range']=[float(rows.min()),float(rows.max())];out['col_scale_range']=[float(cols.min()),float(cols.max())]
    # 1,2: gains with verified adjoint
    fwd=lambda x:cols[:,None]*inv.apply(rows[:,None]*x,solve=True);adj=lambda x:rows[:,None]*inv.apply(cols[:,None]*x,solve=True,trans=2)
    r=np.random.default_rng(8);u=r.standard_normal((N,8))+1j*r.standard_normal((N,8));v=r.standard_normal((N,8))+1j*r.standard_normal((N,8))
    a_,b_=np.vdot(v,fwd(u)),np.vdot(adj(v),u);out['adjoint_test_relative']=float(abs(a_-b_)/abs(a_))
    hs=gain(fwd,adj);hr=gain(lambda x:inv.apply(x,solve=True),lambda x:inv.apply(x,solve=True,trans=2))
    out['scaled_gain_history']=hs;out['unscaled_gain_history']=hr
    # 3: leaf conditioning in physical and solver coordinates
    start=0;leaf_rows=[]
    def spans(node,lo):
        if node.leaf:leaf_rows.append((node,lo,lo+node.n));return
        spans(node.left,lo);spans(node.right,lo+node.left.n)
    spans(inv.root,0);phys=[];scal=[];rowonly=[];jac=[]
    for node,lo,hi in leaf_rows:
        a=np.asarray(rebuild(node.lu),complex);ids=perm[lo:hi]
        s=a/rows[ids][:,None]/cols[ids][None,:];ro=a/rows[ids][:,None]
        dr=1/np.abs(a).max(axis=1);own=a*dr[:,None];own=own/np.abs(own).max(axis=0)[None,:]
        phys.append(float(np.linalg.cond(a,1)));scal.append(float(np.linalg.cond(s,1)));rowonly.append(float(np.linalg.cond(ro,1)));jac.append(float(np.linalg.cond(own,1)))
    q=lambda v:[float(np.min(v)),float(np.median(v)),float(np.max(v))]
    out['leaf_cond1_physical']=q(phys);out['leaf_cond1_solver_scaling']=q(scal);out['leaf_cond1_row_scaling_only']=q(rowonly);out['leaf_cond1_own_row_col_max_scaling']=q(jac)
    # 4: attribution
    for x in nodes(inv.root):
        if x.lu is not None:x._a=rebuild(x.lu)
    for node,lo,hi in leaf_rows:
        ids=perm[lo:hi];a=np.asarray(node._a,complex)
        node._dr=1/rows[ids];node._slu=la.lu_factor(a*node._dr[:,None])
        node._dr2=1/np.abs(a).max(axis=1);t=a*node._dr2[:,None];node._dc=1/np.abs(t).max(axis=0);node._slu2=la.lu_factor(t*node._dc[None,:])
    modes={'double':set(),'leaf':{'leaf'},'small':{'small'},'prod':{'prod'},'leaf+small':{'leaf','small'},'small+prod':{'small','prod'},'leaf+prod':{'leaf','prod'},'leafscaled(solver rows)':{'leafscaled'},'leafscaled(own max rows+cols)':{'leafscaled2'},'leafscaled+small':{'leafscaled','small'},'all':{'leaf','small','prod'}}
    res={}
    for name,x in (('random',u),('random2',v)):
        b=(rows[:,None]*x)[perm];outs={}
        for m,s in modes.items():
            t=time.perf_counter();y=apply(inv.root,b.astype(LD) if s-{'leafscaled','leafscaled2'} else b,s);outs[m]=y;print(name,m,round(time.perf_counter()-t,1),flush=True)
        prod_ref=inv.apply(rows[:,None]*x,solve=True)[perm]
        ref=outs['all'];scale=cols[perm][:,None]
        res[name]={m:float(la.norm(np.asarray(scale*(y-ref),complex))/la.norm(np.asarray(scale*ref,complex))) for m,y in outs.items() if m!='all'}
        res[name]['production_apply_vs_all_extended']=float(la.norm(np.asarray(scale*(prod_ref-ref),complex))/la.norm(np.asarray(scale*ref,complex)))
        res[name]['my_double_vs_production_apply']=float(la.norm(outs['double']-prod_ref)/la.norm(prod_ref))
        res[name]['unscaled_coordinates']={m:float(la.norm(np.asarray(y-ref,complex))/la.norm(np.asarray(ref,complex))) for m,y in outs.items() if m!='all'}
    out['error_vs_all_extended_reference_solver_coordinates']=res
    Path(sys.argv[1]).write_text(json.dumps(out,indent=1));print(json.dumps({k:v for k,v in out.items() if 'history' not in k},indent=1));print('scaled',hs[-3:],'raw',hr[-3:])
