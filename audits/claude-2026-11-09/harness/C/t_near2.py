import sys, numpy as np, time
from ref import *
import ghost_backend.bor.kernels as K
import ghost_backend.bor.streaming as S
from numpy.polynomial.legendre import leggauss
def graded_ref(fun, modes, kabs, amax, nfun):
    """int_{-pi}^{pi} F(xi) e^{-j m xi} dxi by dyadic composite Gauss toward 0 on both halves. fun(xi)->list of [n,na]"""
    x,w=leggauss(48)
    edges=[np.pi*2.0**-j for j in range(0,46)]+[0.0]
    # split outer panels for oscillation
    nsub=int(np.ceil((kabs*amax+max(abs(modes)))/6))+1
    xs=[];ws=[]
    for a,b in zip(edges[1:],edges[:-1]):
        sub=nsub if b>0.01 else 1
        for i in range(sub):
            lo=a+(b-a)*i/sub; hi=a+(b-a)*(i+1)/sub
            xs.append(lo+(x+1)/2*(hi-lo)); ws.append(w/2*(hi-lo))
    xs=np.concatenate(xs); ws=np.concatenate(ws)
    out=[0]*nfun
    for sgn in (1,-1):
        F=fun(sgn*xs)
        E=np.exp(-1j*sgn*xs[:,None]*modes[None,:])*ws[:,None]
        for i in range(nfun): out[i]=out[i]+F[i]@E
    return out
def check(P, k, m_max, label, native=True):
    P=[np.asarray(a,float) for a in P]; n=len(P[0])
    saved=S._NATIVE; ne=K._native_entry
    if not native:
        S._NATIVE=None; K._native_entry=lambda name: None
    try:
        modes=np.arange(m_max+2)
        amax=float(np.max(2*np.sqrt(P[0]*P[4])))
        ref=graded_ref(lambda xi:[green((P[0],P[1],P[4],P[5]),k,xi)],modes,abs(k),amax,1)[0]
        t=time.time(); g=K.modal_kernels_near(P[0],P[1],P[4],P[5],k,m_max); tg=time.time()-t
        eg=np.max(np.abs(g-ref),axis=1)/np.max(np.abs(ref),axis=1)
        s=f'{label:28s} nat={int(native)} G {eg.max():.1e}'
        sm=np.arange(-m_max,m_max+1)
        for kind,fn in (('mfie',K.mfie_kernels_near),('ibc',K.ibc_kernels_near)):
            refb=graded_ref(lambda xi:vec_brackets(kind,P,k,xi),sm,abs(k),amax,4)
            b=fn(*P,k,m_max)
            sc=np.max([np.max(np.abs(r),axis=1) for r in refb],axis=0)
            e=[np.max(np.max(np.abs(x-r),axis=1)/sc) for x,r in zip(b,refb)]
            s+=f' | {kind} '+' '.join(f'{v:.0e}' for v in e)
            b2=fn(*P,k,m_max,signed=False)
            e2=max(np.max(np.abs(x-y[:,m_max:])) /sc.max() for x,y in zip(b2,b))
            if e2>1e-12: s+=f' UNSIGNED-MISMATCH {e2:.1e}'
        print(s, flush=True)
    except Exception as ex:
        print(f'{label:28s} nat={int(native)} EXC {type(ex).__name__}: {str(ex)[:150]}', flush=True)
    finally:
        S._NATIVE=saved; K._native_entry=ne
def mk(rp,zp,rq,zq,ap=0.3,aq=1.1):
    rp,zp,rq,zq=np.broadcast_arrays(*[np.atleast_1d(np.asarray(v,float)) for v in (rp,zp,rq,zq)])
    o=np.ones_like(rp)
    return (rp,zp,np.cos(ap)*o,np.sin(ap)*o,rq,zq,np.cos(aq)*o,np.sin(aq)*o)
ds=np.array([1e-1,1e-2,1e-3,1e-4,1e-5,1e-6,1e-7])
d3=np.array([1e-1,1e-2,1e-3])
check(mk(1.0,0.0,1.0+d3*0.6,d3*0.8),20.0,8,'close d>=1e-3 (ref clean)',True)
check(mk(8.0,0.0,8.0+d3*0.6,d3*0.8),20.0,30,'rho=8 k*rho=160 m30',True)
for native in (False,):
    check(mk(1.0,0.0,1.0+ds*0.6,ds*0.8),20.0,8,'close pairs rho=1',native)
    check(mk(1.0,0.0,1.0+ds*0.6,ds*0.8,0.3,0.3),20.0,8,'close collinear',native)
    check(mk(1.0,0.0,1.0+ds*0.6,ds*0.8),20-30j,8,'close lossy',native)
    check(mk([1e-3,1e-6,1e-9,1e-12,1e-15,1e-17],0.0,[2e-3,1e-2,1e-2,1e-2,1e-2,1e-2],0.01),20.0,8,'near axis p',native)
    check(mk([1e-2,1e-2,1e-2],0.0,[1e-6,1e-12,0.0],0.01),20.0,8,'near axis q',native)
    check(mk([1e-5,1e-8,0.0],0.0,[2e-5,3e-8,0.0],[1e-5,1e-8,1e-3]),20.0,8,'both near axis',native)
