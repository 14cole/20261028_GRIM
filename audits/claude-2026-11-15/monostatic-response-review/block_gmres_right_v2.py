"""Research variant (reviewer): right-preconditioned rank-aware block GMRES.

With right preconditioning the Arnoldi least-squares residual is the residual of
the original system, so it is used only as a trigger: the true residual of every
original RHS is evaluated when the projected residual reaches the target (and at
restart/breakdown), and acceptance is on the true residual alone. If a true check
fails, the cycle restarts immediately from the true residual (v2).
"""
import time
import numpy as np
from scipy.linalg import lstsq,norm
from block_gmres import _basis

def solve(apply,precondition,b,rtol=1e-12,restart_blocks=20,max_cycles=10,check_every=None):
    b=np.asarray(b,complex);n,m=b.shape;x=np.zeros_like(b);bn=np.linalg.norm(b,axis=0);target=rtol*bn
    ac=pc=steps=rhs_apps=pre_rhs_apps=true_checks=failed_checks=0;started=time.perf_counter();ranks=[];peak_columns=0;history=[]
    def a(v):
        nonlocal ac,rhs_apps
        ac+=1;rhs_apps+=v.shape[1];return apply(v)
    def pre(v):
        nonlocal pc,pre_rhs_apps
        pc+=1;pre_rhs_apps+=v.shape[1];return precondition(v)
    residual=b.copy();rn=bn.copy();safety=1.0
    for cycle in range(max_cycles):
        if cycle:
            residual=b-a(x);rn=np.linalg.norm(residual,axis=0);true_checks+=1
        if np.all(rn<=target):break
        q,beta=_basis(residual,norm(residual));r0=q.shape[1]
        capacity=(restart_blocks+1)*m
        V=np.zeros((n,capacity),complex);H=np.zeros((capacity,restart_blocks*m),complex);G=np.zeros((capacity,m),complex)
        V[:,:r0]=q;G[:r0]=beta;lo=0;hi=r0;total=r0;done=False
        for step in range(restart_blocks):
            w=a(pre(V[:,lo:hi]));reference_norm=norm(w);steps+=1
            for repeat in range(2):
                h=V[:,:total].conj().T@w
                H[:total,lo:hi]+=h;w-=V[:,:total]@h
            qnext,r=_basis(w,reference_norm);width=qnext.shape[1];ranks.append(width)
            H[total:total+width,lo:hi]=r;V[:,total:total+width]=qnext;total+=width
            peak_columns=max(peak_columns,total)
            coefficients=lstsq(H[:total,:hi],G[:total],cond=None,lapack_driver='gelsy')[0]
            projected=np.linalg.norm(G[:total]-H[:total,:hi]@coefficients,axis=0)
            last=step+1==restart_blocks or width==0
            if not last and not np.all(projected<=safety*target):
                lo,hi=hi,total;continue
            candidate=x+pre(V[:,:hi]@coefficients);candidate[:,bn==0]=0
            residual=b-a(candidate);rn=np.linalg.norm(residual,axis=0);true_checks+=1
            history.append(dict(step=steps,max_projected=float(np.max(projected/np.maximum(bn,1e-300))),max_true=float(np.max(rn/np.maximum(bn,1e-300)))))
            if np.all(rn<=target):
                x=candidate;done=True;break
            # v2: a failed true check means this cycle has reached its attainable
            # residual (projected and true have separated). Restart from the true
            # residual at once instead of extending the same Arnoldi basis.
            failed_checks+=1;x=candidate;break
        if done:break
    else:raise RuntimeError('Right block GMRES did not converge: '+str(rn/np.maximum(bn,1e-300)))
    rel=np.divide(rn,bn,out=np.zeros_like(rn),where=bn!=0)
    assert np.isfinite(x).all() and np.max(rel)<=rtol
    return x,dict(algorithm='right_preconditioned_rank_aware_block_gmres',columns=m,steps=steps,cycles=cycle+1,matrix_applications=ac,preconditioner_applications=pc,rhs_equivalent_matrix_applications=rhs_apps,preconditioner_rhs_applications=pre_rhs_apps,true_checks=true_checks,failed_true_checks=failed_checks,trigger_safety=safety,check_history=history,max_scaled_relative_residual=float(max(rel)),seconds=time.perf_counter()-started,krylov_vector_capacity_bytes=(restart_blocks+1)*n*m*16,peak_basis_columns=peak_columns,next_block_ranks=ranks)
