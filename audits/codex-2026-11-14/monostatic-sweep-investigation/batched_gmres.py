"""Research batched independent left-preconditioned GMRES (CGS2).

Each column has its own Krylov polynomial and least-squares problem. Matrix
applications share the FMM traversal. This is NOT a block Krylov space and does
not deflate or mix illuminations. True residuals of every original RHS decide
acceptance. All-zero/duplicate RHS columns are supported.
"""
import time
import numpy as np
from scipy.linalg import lstsq

def solve(apply,precondition,b,rtol=1e-12,restart=80,max_cycles=10,check_every=8):
    b=np.asarray(b,complex);n,m=b.shape;x=np.zeros_like(b)
    norm=np.linalg.norm(b,axis=0);target=rtol*norm;ac=pc=0;steps=0;started=time.perf_counter()
    def a(v):
        nonlocal ac
        ac+=1;return apply(v)
    def pre(v):
        nonlocal pc
        pc+=1;return precondition(v)
    for cycle in range(max_cycles):
        residual=b-a(x);rn=np.linalg.norm(residual,axis=0)
        if np.all(rn<=target):break
        z=pre(residual);beta=np.linalg.norm(z,axis=0)
        V=np.zeros((restart+1,n,m),complex);H=np.zeros((restart+1,restart,m),complex)
        V[0]=np.divide(z,beta[None,:],out=np.zeros_like(z),where=beta[None,:]!=0)
        for j in range(restart):
            w=pre(a(V[j]));steps+=1
            # Twice-orthogonalized classical Gram-Schmidt, independently per RHS.
            for repeat in range(2):
                h=np.einsum('inm,nm->im',V[:j+1].conj(),w,optimize=True)
                H[:j+1,j]+=h;w-=np.einsum('inm,im->nm',V[:j+1],h,optimize=True)
            normw=np.linalg.norm(w,axis=0);H[j+1,j]=normw
            V[j+1]=np.divide(w,normw[None,:],out=np.zeros_like(w),where=normw[None,:]!=0)
            if (j+1)%check_every and j+1!=restart and not np.any(normw==0):continue
            c=np.empty((j+1,m),complex)
            for column in range(m):
                e=np.zeros(j+2,complex);e[0]=beta[column]
                c[:,column]=lstsq(H[:j+2,:j+1,column],e,cond=None,lapack_driver='gelsy')[0]
            candidate=x+np.einsum('inm,im->nm',V[:j+1],c,optimize=True)
            residual=b-a(candidate);rn=np.linalg.norm(residual,axis=0)
            if np.all(rn<=target):
                x=candidate;break
        else:
            x=candidate;continue
        x=candidate
        if np.all(rn<=target):break
    else:raise RuntimeError('Batched GMRES did not converge: '+str(rn/np.maximum(norm,1e-300)))
    rel=np.divide(rn,norm,out=np.zeros_like(rn),where=norm!=0)
    assert np.isfinite(x).all() and np.max(rel)<=rtol
    return x,dict(columns=m,steps=steps,cycles=cycle+1,matrix_applications=ac,preconditioner_applications=pc,rhs_equivalent_matrix_applications=ac*m,max_scaled_relative_residual=float(max(rel)),seconds=time.perf_counter()-started,krylov_vector_capacity_bytes=(restart+1)*n*m*16)
