import sys, os, time
sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
import numpy as np, scipy.special as sp
from ghost_backend.compressed import hmatrix as HM
from ghost_backend.execution.options import execution_scope, DEFAULTS

class DenseOracle:
    def __init__(s,A): s.A=A; s.n=len(A); s.calls=0; s.entries=0
    def get_with_error(s,rows,cols):
        s.calls+=1; s.entries+=len(rows)*len(cols)
        v=s.A[np.ix_(rows,cols)]
        return v, np.zeros(v.shape)

def kernel(xy, ka, w):
    d=np.linalg.norm(xy[:,None]-xy[None],axis=2)
    same=d<1e-14
    d[same]=w/4
    A=0.25j*sp.hankel1(0,ka*d)*w
    return A

def circle(n,x0=0.,r=1.):
    th=2*np.pi*(np.arange(n)+.5)/n
    return np.c_[x0+r*np.cos(th), r*np.sin(th)]

def test(name, A, xy, radius, threads=2, tol=HM.TOLERANCE, verbose=True):
    n=len(A)
    with execution_scope(dict(DEFAULTS,assembly_threads=threads,blas_threads=1)):
        t=time.time()
        try:
            op=HM.HMatrixOperator(DenseOracle(A), xy, radius, tolerance=tol, budget=8<<30)
        except Exception as e:
            print(name,'REJECTED',type(e).__name__,str(e)[:150]); return None
        tb=time.time()-t
        # full reconstruction error per row
        P=op.order
        Ap=A[np.ix_(P,P)]
        Hd=np.empty_like(Ap)
        step=256
        for s in range(0,n,step):
            Hd[s:s+step]=op._get_positions(np.arange(s,min(n,s+step)),np.arange(n))
        rowerr=np.abs(Ap-Hd).sum(1); norm=np.abs(Ap).sum(1).max()
        rng=np.random.default_rng(3); x=rng.standard_normal((n,4))+1j*rng.standard_normal((n,4))
        t=time.time(); y=op.matmul(x); tm=time.time()-t
        e0=np.abs(y-A@x).max()/np.abs(A@x).max()
        e1=np.abs(op.matmul(x,1)-A.T@x).max()/np.abs(A.T@x).max()
        e2=np.abs(op.matmul(x,2)-A.conj().T@x).max()/np.abs(A@x).max()
        ev=op.evidence
        if verbose: print(name,'n',n,'thr',threads,'build %.1fs matmul(4) %.3fs'%(tb,tm),'TRUE max row err/norm %.2e (mean %.2e)'%(rowerr.max()/norm,rowerr.mean()/norm),
              'sampled_row_error %.2e'%op.sampled_row_error,'ratio true/sampled %.1f'%(rowerr.max()/norm/max(op.sampled_row_error,1e-300)),
              'opnorm est %.4g true %.4g'%(op.operator_norm,norm),'matmul err %.1e T %.1e H %.1e'%(e0,e1,e2),
              'bytes/dense %.3f'%(op.bytes/(16*n*n)),'max_rank',ev['max_rank'],'mean',round(ev['mean_rank'],1),'coef frac %.3f'%ev['coefficient_fraction'],'lists',ev['interaction_lists'],'dense lists',ev['dense_interaction_lists'],'sample rows',ev['sampled_rows'],'leaf',op.leaf)
        return op, y, Hd

w=lambda n:2*np.pi/n
n=4000
xy=circle(n); A=kernel(xy,40.,w(n))+0.5*np.eye(n)
r=np.full(n,w(n))
o2=test('circle ka=40',A,xy,r,threads=2)
o1=test('circle ka=40',A,xy,r,threads=1)
o4=test('circle ka=40',A,xy,r,threads=4)
print('determinism across threads: matmul bitwise 1v2',np.array_equal(o1[1],o2[1]),'1v4',np.array_equal(o1[1],o4[1]),'entries bitwise 1v2',np.array_equal(o1[2],o2[2]),'1v4',np.array_equal(o1[2],o4[2]), 'max diff', np.abs(o1[2]-o4[2]).max())
o2b=test('circle ka=40 repeat',A,xy,r,threads=2,verbose=False); print('run-to-run bitwise', np.array_equal(o2[2],o2b[2]))
xy=circle(n); A=kernel(xy,400.,w(n))+0.5*np.eye(n); test('circle ka=400 (10 pts/λ)',A,xy,r)
# two nearly touching circles
h=n//2; xy=np.r_[circle(h),circle(h,x0=2.002)]; A=kernel(xy,40.,w(h))+0.5*np.eye(n); test('two circles gap 2e-3',A,xy,np.full(n,w(h)))
# 2-density interleaved (coincident coordinates)
m=2000; xy1=circle(m); K1=kernel(xy1,40.,w(m)); K2=kernel(xy1,80.,w(m))
B=np.block([[K1+0.5*np.eye(m), -K2],[K2+0.5*np.eye(m), 1.7*K1]]); test('2-density coincident',B,np.tile(xy1,(2,1)),np.full(2*m,w(m)))
# badly scaled rows (row norms differing by 1e8): error is relative to global ||A||inf
S=np.ones(n); S[::2]=1e-8; xy=circle(n); A=(kernel(xy,40.,w(n))+0.5*np.eye(n))*S[:,None]
res=test('row-scaled 1e-8 on even rows',A,xy,r)
if res:
    op,_,Hd=res; P=op.order; Ap=A[np.ix_(P,P)]
    rel=np.abs(Ap-Hd).sum(1)/np.abs(Ap).sum(1); print('   per-row RELATIVE error max %.2e (small rows) '%rel.max())
