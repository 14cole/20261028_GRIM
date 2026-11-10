import sys, time, os
sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
import numpy as np, scipy.linalg as la, scipy.special as sp
from ghost_backend.linalg import hierarchical as H

def kernel(n, ka, two_body_gap=None, seed=0):
    th = 2*np.pi*(np.arange(n)+.5)/n
    xy = np.c_[np.cos(th), np.sin(th)]
    if two_body_gap is not None:
        h=n//2
        th = 2*np.pi*(np.arange(h)+.5)/h
        xy = np.r_[np.c_[np.cos(th), np.sin(th)], np.c_[np.cos(th)+2+two_body_gap, np.sin(th)]]
    d = np.linalg.norm(xy[:,None]-xy[None],axis=2)
    w = 2*np.pi/n
    np.fill_diagonal(d, w/4)
    A = 0.25j*sp.hankel1(0, ka*d)*w
    A += 0.5*np.eye(n)
    return A, xy

def run(name, A, xy, nrhs=8, expect=None):
    n=len(A)
    rng=np.random.default_rng(1)
    b=rng.standard_normal((n,nrhs))+1j*rng.standard_normal((n,nrhs))
    t=time.time()
    try:
        f=H.HierarchicalFactor(A, xy)
    except Exception as e:
        print(name,'REJECTED',type(e).__name__,str(e)[:100],'t=%.2f'%(time.time()-t)); return None
    tb=time.time()-t
    t=time.time(); x=f.solve(b); ts=time.time()-t
    t=time.time(); lu=la.lu_factor(A); xr=la.lu_solve(lu,b); tl=time.time()-t
    raw=f._apply(b,0)
    ninf=np.abs(A).sum(1).max()
    be=lambda x:(np.abs(A@x-b).max(0)/(ninf*np.abs(x).max(0)+np.abs(b).max(0))).max()
    xt=f.solve(b,trans=1); xh=f.solve(b,trans=2)
    print(name,'n',n,'build %.2fs solve %.2fs lu %.2fs'%(tb,ts,tl),'rel diff vs LU %.2e'%(np.linalg.norm(x-xr)/np.linalg.norm(xr)),
          'raw apply rel %.2e'%(np.linalg.norm(raw-xr)/np.linalg.norm(xr)),'be %.2e be_lu %.2e'%(be(x),be(xr)),
          'T %.2e H %.2e'%(np.linalg.norm(A.T@xt-b)/np.linalg.norm(b),np.linalg.norm(A.conj().T@xh-b)/np.linalg.norm(b)),
          'cond1 %.2e'%np.linalg.cond(A,1) if n<=3000 else '', {k:f.evidence[k] for k in ('builds','tighter_rebuilds','leaves','max_rank','max_block_error','tolerance','factor_bytes','refinements','ordered_copy')}, 'ratio bytes %.3f'%(f.evidence['factor_bytes']/A.nbytes))
    return f

A,xy=kernel(2000, 20.); run('circle ka=20',A,xy)
A,xy=kernel(3000, 200.); run('circle ka=200',A,xy)
A,xy=kernel(3000, 50., two_body_gap=1e-3); run('two close bodies',A,xy)
# no coordinates
A,xy=kernel(2000, 20.); run('circle no coords',A,None)
# interleaved coords (two densities at the same point): [u;q] structure
n=1500; A1,xy=kernel(n,20.); A2,_=kernel(n,35.)
B=np.block([[A1, -A2*0.7],[A2+np.eye(n), A1*1.3]]); run('2-density with coords',B,np.tile(xy,(2,1)))
run('2-density NO coords',B,None)
# random dense (incompressible)
rng=np.random.default_rng(0)
R=rng.standard_normal((2000,2000))+1j*rng.standard_normal((2000,2000)); run('random dense',R+50*np.eye(2000),None)
# ill-conditioned low-rank-structured: first kind (no identity), cond grows
n=2000; A,xy=kernel(n,20.); A-=0.5*np.eye(n); print('cond first-kind',np.linalg.cond(A,1)); run('first-kind',A,xy)
# near-singular: kernel + make nearly singular
A,xy=kernel(2000,20.); u,s,vh=np.linalg.svd(A); s[-1]=1e-11*s[0]; A2=(u*s)@vh; run('near singular 1e11',A2,xy)
s[-1]=1e-14*s[0]; A2=(u*s)@vh; run('near singular 1e14',A2,xy)
