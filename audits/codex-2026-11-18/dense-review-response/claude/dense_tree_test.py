"""Reviewer T1: real DenseFactor of one source tree on a synthetic suite; outputs saved for cross-tree comparison.
argv: label, out prefix. Written before reading Codex's check_dense.py."""
import os,sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.execution.cpu import CPUState,_STATE
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
from ghost_backend.linalg.dense import DenseFactor
import ghost_backend.linalg.dense as dense_module
label,out=sys.argv[1],sys.argv[2];r=np.random.default_rng(20261118);arrays={};records=[]
src=Path(dense_module.__file__).read_text();patched='np.matmul(self.a, candidate, out=residual)' in src
def cmat(n):return r.standard_normal((n,n))+1j*r.standard_normal((n,n))
def with_cond(n,cond):
    u,_=np.linalg.qr(cmat(n));v,_=np.linalg.qr(cmat(n));s=np.logspace(0,-np.log10(cond),n);return (u*s)@v.conj().T
n=160
mats={'well':cmat(n)+n*np.eye(n),'rows_1e12':(cmat(n)+n*np.eye(n))*np.logspace(-6,6,n)[:,None],'cols_1e12':(cmat(n)+n*np.eye(n))*np.logspace(-6,6,n)[None,:],
      'cond_1e6':with_cond(n,1e6),'cond_1e10':with_cond(n,1e10),'cond_1e12':with_cond(n,1e12),'cond_1e13':with_cond(n,1e13),'cond_1e15':with_cond(n,1e15),
      'tiny_scale_1e-150':(cmat(n)+n*np.eye(n))*1e-150,'huge_scale_1e150':(cmat(n)+n*np.eye(n))*1e150}
def rhs_variants(width):
    base=r.standard_normal((n,width))+1j*r.standard_normal((n,width));v={'F':np.asfortranarray(base),'C':np.ascontiguousarray(base)}
    v['strided']=np.repeat(base,2,axis=1)[:,::2];v['real']=base.real.copy()
    z=base.copy();z[:,0]=0;v['zero_column']=z
    if width==1:v['vector']=base[:,0].copy()
    return v
with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
    for mname,m in mats.items():
        for order in ('F','C'):
            a=np.asfortranarray(m) if order=='F' else np.ascontiguousarray(m)
            try:f=DenseFactor(a.copy(order=order),owned_matrix=True,force_double=True)
            except Exception as e:
                records.append(dict(matrix=mname,order=order,construct_error=type(e).__name__+': '+str(e)[:120]));continue
            stored=f.a;info=dict(stored_type=type(stored).__name__,stored_f=bool(getattr(getattr(stored,'flags',None),'f_contiguous',False)),stored_dtype=str(getattr(stored,'dtype','')))
            for width in (1,2,3,8,15,16,17,64):
                for vname,b in rhs_variants(width).items():
                    key=f'{mname}|{order}|{width}|{vname}';e0=dict(f.event)
                    try:
                        x=f.solve(b);arrays[key]=np.asarray(x);res=dict(ok=True,shape=list(np.shape(x)),order='F' if np.asarray(x).flags.f_contiguous else 'C')
                    except Exception as e:res=dict(ok=False,error=type(e).__name__+': '+str(e)[:160])
                    ev={k:(f.event.get(k,0)-e0.get(k,0)) if isinstance(f.event.get(k),(int,float)) and not isinstance(f.event.get(k),bool) and k in ('refinements','refinement_steps','rhs_batches','residual_products_reused') else None for k in f.event}
                    records.append(dict(key=key,**info,**res,max_backward_error=f.event.get('max_backward_error'),max_equilibrated_backward_error=f.event.get('max_equilibrated_backward_error'),event_delta={k:v for k,v in ev.items() if v is not None},event_keys=sorted(f.event)))
    # direct comparison of the two residual expressions
    direct=[]
    for mname in ('well','rows_1e12','cond_1e12'):
        a=np.asfortranarray(mats[mname])
        for width in (1,2,3,8,15,16):
            for layout in ('F','C','strided'):
                x=rhs_variants(width)[layout].astype(complex);b=np.asfortranarray(r.standard_normal((n,width))+0j)
                old=a@x-b;new=np.empty(x.shape,np.complex128,order='F');np.matmul(a,x,out=new);new-=b
                direct.append(dict(matrix=mname,width=width,layout=layout,bitwise=bool(np.array_equal(old,new)),max_abs_diff=float(np.max(abs(old-new))),scale=float(np.max(abs(old)))))
np.savez(out+'.npz',**arrays);json.dump(dict(label=label,patched=patched,records=records,direct=direct),open(out+'.json','w'),indent=1)
print(label,'patched',patched,'solves',len(arrays),'failed',sum(1 for x in records if x.get('ok') is False),'construct errors',sum(1 for x in records if 'construct_error' in x),'direct non-bitwise',sum(1 for d in direct if not d['bitwise']))
