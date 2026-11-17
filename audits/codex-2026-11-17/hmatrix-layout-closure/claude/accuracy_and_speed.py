"""Reviewer checks T1 (distance from an exact dense solve) and T2 (apply speed by factor layout).
argv: label, mode ('asis'|'fortran_e'), n, kind, k, out.npz, timing(0/1)"""
import os,sys,json,time
import numpy as np,scipy.linalg as la
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import (mesh_for,SimpleNamespace,NativeOracle,HMatrixOperator,HMatrixFactor,HMatrixSystem,support_radius,CPUState,_STATE,cpu_allocation_scope,execution_scope,dielectric)
label,mode,n,kind,k,out,timing=sys.argv[1],sys.argv[2],int(sys.argv[3]),sys.argv[4],float(sys.argv[5]),sys.argv[6],int(sys.argv[7]);eps=3-.08j
def walk(node):
    if node.leaf:return
    for key in ('e1','e2'):
        if mode=='fortran_e':setattr(node,key,np.asfortranarray(getattr(node,key)))
    walk(node.left);walk(node.right)
init0=HMatrixSystem.__init__
def init(self,*a,**kw):
    init0(self,*a,**kw);walk(self.root)
HMatrixSystem.__init__=init
res={}
with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
    mesh=mesh_for(n,kind);info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
    coords=np.tile(np.array([x.xy for x in mesh.nodes]),(2,1));oracle=NativeOracle(mesh,[info],'TE',k,'dielectric')
    h=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=12*2**30);b=dielectric.rhs_many(mesh,k,np.linspace(-90,90,16,endpoint=False))
    f=HMatrixFactor(h,storage_budget_bytes=12*2**30)
    res['single']=np.column_stack([f.solve(b[:,j:j+1])[:,0] for j in range(b.shape[1])]);res['block']=f.solve(b);res['rhs']=b
    if not timing:
        A=dielectric.assemble_system(mesh,[info],'TE',k);res['exact']=la.solve(A,b);res['dense_residual']=np.linalg.norm(A@res['exact']-b,axis=0)/np.linalg.norm(b,axis=0)
        res['residual_single']=np.linalg.norm(A@res['single']-b,axis=0)/np.linalg.norm(b,axis=0)
    else:
        r=np.random.default_rng(1);p1=r.standard_normal((2*n,1))+1j*r.standard_normal((2*n,1));p180=np.asfortranarray(r.standard_normal((2*n,180))+1j*r.standard_normal((2*n,180)))
        inv=f.factor;T={}
        for name,p,reps in (('apply_1',p1,200),('apply_180',p180,30)):
            inv.apply(p,solve=True);ts=[]
            for _ in range(reps):
                t=time.perf_counter();inv.apply(p,solve=True);ts.append(time.perf_counter()-t)
            T[name]=dict(median=float(np.median(ts)),q10=float(np.quantile(ts,.1)),q90=float(np.quantile(ts,.9)),reps=reps)
        ts=[]
        for _ in range(5):
            t=time.perf_counter();f.solve(b);ts.append(time.perf_counter()-t)
        T['refined_solve_16']=dict(median=float(np.median(ts)),q10=float(min(ts)),q90=float(max(ts)),reps=5)
        json.dump(dict(label=label,mode=mode,timing=T,inverse_bytes=int(inv.bytes),tolerance=f.tolerance),open(out.replace('.npz','.timing.json'),'w'),indent=1);print(label,mode,{a:round(v['median']*1e3,3) for a,v in T.items()})
np.savez(out,**res);print('done',label,mode,kind,2*n)
