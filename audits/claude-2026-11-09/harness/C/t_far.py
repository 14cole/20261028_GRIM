import sys, os, numpy as np, time
from ref import *
import ghost_backend.bor.kernels as K
import ghost_backend.bor.streaming as S
print('native', S._NATIVE)
rng=np.random.default_rng(1)
def pairs(n, scale=1.0, gapmin=0.02):
    rp=rng.uniform(0,1,n)*scale; rq=rng.uniform(0,1,n)*scale; zp=rng.uniform(-1,1,n)*scale; zq=rng.uniform(-1,1,n)*scale
    # some near axis
    rp[:n//8]=rng.uniform(0,1e-6,n//8)*scale; rq[n//8:n//4]=rng.uniform(0,1e-9,n//4-n//8)*scale
    a1=rng.uniform(0,2*np.pi,n); a2=rng.uniform(0,2*np.pi,n)
    d=np.hypot(rp-rq,zp-zq); keep=d>gapmin*scale
    return [x[keep] for x in (rp,zp,np.cos(a1),np.sin(a1),rq,zq,np.cos(a2),np.sin(a2))]
def run(k, m_max, label, scale=1.0, gapmin=0.02):
    P=pairs(120, scale, gapmin); n=len(P[0])
    N=1<<13; xi=2*np.pi*np.arange(N)/N-np.pi
    modes=np.arange(m_max+2)
    refg=modal_trap(green((P[0],P[1],P[4],P[5]),k,xi),xi,modes)
    near=np.zeros(n,bool)
    res={}
    bm=np.arange(m_max+1)
    REF={kind:[modal_trap(F,xi,bm) for F in vec_brackets(kind,P,k,xi)] for kind in ('mfie','ibc')}
    for native in (True,False):
        saved=S._NATIVE
        if not native: S._NATIVE=None
        try:
          for meth in ('auto','complex','real','fft'):
            if meth!='auto':
                orig=K._half_grid_projection_method; K._half_grid_projection_method=lambda *a,m=meth:m
            try:
                g=K.banded_modal_kernels('g',(P[0],P[1],P[4],P[5]),k,m_max,near)
                eg=np.max(np.abs(g-refg),axis=1)/np.max(np.abs(refg),axis=1)
                out=[f'{label} native={native} {meth}: G relmax {eg.max():.2e}']
                bm=np.arange(m_max+1)
                for kind in ('mfie','ibc'):
                    refb=REF[kind]
                    b=K.banded_modal_kernels(kind,tuple(P),k,m_max,near,bm)
                    sc=np.max([np.max(np.abs(r),axis=1) for r in refb],axis=0)
                    eb=[np.max(np.max(np.abs(x-r),axis=1)/sc) for x,r in zip(b,refb)]
                    out.append(f'{kind} '+' '.join(f'{e:.1e}' for e in eb))
                    res[(native,meth,kind)]=b
                res[(native,meth,'g')]=g
                print(' | '.join(out))
            finally:
                if meth!='auto': K._half_grid_projection_method=orig
        finally:
            S._NATIVE=saved
    # native vs numpy
    d=max(np.max(np.abs(res[(True,'auto','g')]-res[(False,'auto','g')])/np.max(np.abs(refg))) ,0)
    print('  native-vs-numpy G', d)
    # signed modes
    sm=np.arange(-m_max,m_max+1)
    b=K.banded_modal_kernels('mfie',tuple(P),k,m_max,near)
    refb=[modal_trap(F,xi,sm) for F in vec_brackets('mfie',P,k,xi)]
    print('  signed mfie', [f'{np.max(np.abs(x-r))/np.max(np.abs(r)):.1e}' for x,r in zip(b,refb)])
run(20.0, 12, 'k=20')
run(200.0, 40, 'k=200 ka large')
run(20.0-15j, 12, 'lossy k=20-15j')
run(60-300j, 30, 'very lossy')
run(2.0, 200, 'k=2 m_max=200')
run(20.0e3, 12, 'mm units', scale=1e-3)
