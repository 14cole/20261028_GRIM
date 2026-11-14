"""Research block GMRES: one rank-aware shared Krylov space for multiple RHS.

Left preconditioning; CGS2; QR + small-core SVD for rank deflation. Every
original RHS must pass its true scaled residual. No acceptance from projected
residual alone. This is distinct from batched independent GMRES.
"""
import time
import numpy as np
from scipy.linalg import qr,svd,lstsq,norm

def _basis(value,reference_norm):
    if value.shape[1]==0:return value.copy(),np.empty((0,0),complex)
    q,r=qr(value,mode='economic',check_finite=False)
    u,s,vh=svd(r,full_matrices=False,check_finite=False)
    rank=int(np.count_nonzero(s>1e-14*reference_norm))
    return q@u[:,:rank],s[:rank,None]*vh[:rank]

def solve(apply,precondition,b,rtol=1e-12,restart_blocks=20,max_cycles=10,check_every=1):
    if not isinstance(check_every,int) or check_every<1:raise ValueError("check_every must be a positive integer")
    b=np.asarray(b,complex);n,m=b.shape;x=np.zeros_like(b);bn=np.linalg.norm(b,axis=0);target=rtol*bn
    ac=pc=steps=rhs_apps=pre_rhs_apps=0;started=time.perf_counter();ranks=[];peak_columns=0
    def a(v):
        nonlocal ac,rhs_apps
        ac+=1;rhs_apps+=v.shape[1];return apply(v)
    def pre(v):
        nonlocal pc,pre_rhs_apps
        pc+=1;pre_rhs_apps+=v.shape[1];return precondition(v)
    for cycle in range(max_cycles):
        residual=b-a(x);rn=np.linalg.norm(residual,axis=0)
        if np.all(rn<=target):break
        z=pre(residual);q,beta=_basis(z,norm(z));r0=q.shape[1]
        if r0==0:raise RuntimeError('Preconditioned residual lost all rank before true convergence')
        capacity=(restart_blocks+1)*m
        V=np.zeros((n,capacity),complex);H=np.zeros((capacity,restart_blocks*m),complex);G=np.zeros((capacity,m),complex)
        V[:,:r0]=q;G[:r0]=beta;lo=0;hi=r0;total=r0
        for step in range(restart_blocks):
            w=pre(a(V[:,lo:hi]));reference_norm=norm(w);steps+=1
            for repeat in range(2):
                h=V[:,:total].conj().T@w
                H[:total,lo:hi]+=h;w-=V[:,:total]@h
            qnext,r=_basis(w,reference_norm);width=qnext.shape[1];ranks.append(width)
            H[total:total+width,lo:hi]=r;V[:,total:total+width]=qnext;total+=width
            peak_columns=max(peak_columns,total)
            if (step+1)%check_every and step+1!=restart_blocks and width:
                lo,hi=hi,total
                continue
            coefficients=lstsq(H[:total,:hi],G[:total],cond=None,lapack_driver='gelsy')[0]
            candidate=x+V[:,:hi]@coefficients
            # SVD/QR can introduce roundoff in an exactly zero RHS coefficient
            # column. Its exact solution is zero; retain that invariant before
            # checking every original residual, whose zero-RHS target is zero.
            candidate[:,bn==0]=0
            residual=b-a(candidate);rn=np.linalg.norm(residual,axis=0)
            if np.all(rn<=target):
                x=candidate;break
            if width==0:
                x=candidate;break
            lo,hi=hi,total
        else:
            x=candidate;continue
        if np.all(rn<=target):break
    else:raise RuntimeError('Block GMRES did not converge: '+str(rn/np.maximum(bn,1e-300)))
    rel=np.divide(rn,bn,out=np.zeros_like(rn),where=bn!=0)
    assert np.isfinite(x).all() and np.max(rel)<=rtol
    return x,dict(algorithm='rank_aware_block_gmres',true_residual_check_interval=check_every,columns=m,steps=steps,cycles=cycle+1,matrix_applications=ac,preconditioner_applications=pc,rhs_equivalent_matrix_applications=rhs_apps,preconditioner_rhs_applications=pre_rhs_apps,max_scaled_relative_residual=float(max(rel)),seconds=time.perf_counter()-started,krylov_vector_capacity_bytes=(restart_blocks+1)*n*m*16,peak_basis_columns=peak_columns,next_block_ranks=ranks)
