"""Independent layout sensitivity check on a dielectric slot and exact matrix.

Actual production code; only newF converts E storage in the research process.
No mesh certification, performance claim, or production source mutation.
"""
import os,sys,json,hashlib
from pathlib import Path
import numpy as np
import scipy.linalg as la
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import (mesh_for, SimpleNamespace, NativeOracle, HMatrixOperator,
    HMatrixFactor, HMatrixSystem, support_radius, CPUState, _STATE,
    cpu_allocation_scope, execution_scope, dielectric, op)
from ghost_backend.execution import memory_budget as mb

label=sys.argv[1]
R=Path(__file__).resolve().parent/'fresh'
arrays={};records=[];builds=[]
init0=HMatrixSystem.__init__
def observe(self,*args,**kwargs):
    init0(self,*args,**kwargs)
    before=self.bytes;stack=[self.root];layouts=[];copy_sizes=[]
    while stack:
        node=stack.pop()
        if node.leaf:continue
        stack.extend([node.left,node.right])
        for key in ('e1','e2'):
            a=getattr(node,key)
            layouts.append(dict(shape=a.shape,c=bool(a.flags.c_contiguous),f=bool(a.flags.f_contiguous)))
            if label=='newF' and not a.flags.f_contiguous:
                copy_sizes.append(a.nbytes)
                setattr(node,key,np.asfortranarray(a))
    assert self.bytes==before
    builds.append(dict(tolerance=self.tolerance,inverse_bytes=before,layouts=layouts,
                       copied_bytes=sum(copy_sizes),largest_single_copy_bytes=max(copy_sizes,default=0)))
HMatrixSystem.__init__=observe
n=1024;k=20.;eps=3-.08j
with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1,'ram_budget_gib':12}):
 with mb.scope(wanted_gib=12) as ledger:
    mesh=mesh_for(n,'slot')
    info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
    coords=np.tile(np.array([x.xy for x in mesh.nodes]),(2,1))
    oracle=NativeOracle(mesh,[info],'TE',k,'dielectric')
    h=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=4*2**30)
    f=HMatrixFactor(h,storage_budget_bytes=4*2**30)
    # Full exact native coefficient matrix, independent of the retained tiles.
    a=dielectric.assemble_system(mesh,[info],'TE',k)
    matrix_sha256=hashlib.sha256(a.tobytes()).hexdigest()
    lu=la.lu_factor(a)
    rng=np.random.default_rng(1982026)
    random_rhs=rng.standard_normal((2*n,8))+1j*rng.standard_normal((2*n,8))
    angles=np.linspace(-90,90,8,endpoint=False)
    physical=dielectric.rhs_many(mesh,k,angles)
    arrays.update(random_rhs=random_rhs,physical_rhs=physical,angles=angles)
    def check(key,b,trans,solve_api=False):
        x=f.solve(b) if solve_api else f.inverse(b,trans=trans)
        reference=la.lu_solve(lu,b,trans=trans)
        aa=a if trans==0 else a.T if trans==1 else a.conj().T
        res=aa@x-b
        xx=x[:,None] if x.ndim==1 else x
        bb=b[:,None] if b.ndim==1 else b
        rr=res[:,None] if res.ndim==1 else res
        rows=np.sum(abs(aa),axis=1)
        backward=float(np.max(abs(rr)/(rows[:,None]*np.max(abs(xx),axis=0)+abs(bb))))
        relative=float(la.norm(x-reference)/max(la.norm(reference),1e-300))
        assert np.isfinite(x).all() and backward<1e-12 and relative<1e-7,(key,backward,relative)
        arrays[key]=x;arrays[key+'__dense']=reference;arrays[key+'__residual']=res;arrays[key+'__row_norm']=rows
        records.append(dict(key=key,trans=trans,shape=x.shape,dense_relative_l2=relative,exact_backward_error=backward))
        return x
    for trans in (0,1,2):
        for width in (1,2,8):
            for order in ('C','F'):
                b=np.array(random_rhs[:,:width],order=order)
                check(f'random_t{trans}_w{width}_{order}',b,trans)
        check(f'random_t{trans}_vector',random_rhs[:,0],trans)
        for width in (1,3):
            arrays[f'raw_t{trans}_w{width}']=f.factor.apply(random_rhs[:,:width],solve=True,trans=trans)
    for width in (1,2,8):
        x=check(f'physical_w{width}',physical[:,:width],0,solve_api=True)
        for suffix,density in (('',x),('__dense',arrays[f'physical_w{width}__dense'])):
            arrays[f'field_w{width}'+suffix]=(op._farfield_linear_density_many(mesh,density[:n],k,angles[:width],'DLP',projection='matched')
                +1j*k*op._farfield_linear_density_many(mesh,density[:n],k,angles[:width],'SLP',projection='matched'))
    assert ledger.pending_construction_bytes==0
    pending=ledger.pending_construction_bytes
np.savez_compressed(R/(label+'-slot.npz'),**arrays)
out=dict(label=label,geometry='slot',panels=n,unknowns=2*n,k=k,eps=[eps.real,eps.imag],
         matrix_sha256=matrix_sha256,checks=records,builds=builds,pending_after=pending,event=f.event,
         scope='One Linux/BLAS configuration; shared native formulation, full exact matrix, no mesh convergence claim. No timing or whole-process memory measurements.')
(R/(label+'-slot.json')).write_text(json.dumps(out,indent=2))
print(json.dumps(dict(label=label,checks=len(records),builds=len(builds),max_backward=max(x['exact_backward_error'] for x in records),max_dense_relative=max(x['dense_relative_l2'] for x in records))))
