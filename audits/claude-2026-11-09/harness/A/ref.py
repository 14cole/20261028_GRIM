import os, sys, math
os.environ.setdefault('OMP_NUM_THREADS','1'); os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
sys.path.insert(0, '/home/user/20261028_GRIM/tools/GHOST')
import numpy as np
from scipy.special import hankel2e
import mpmath as mp
from ghost_backend.twod.geometry import LinearElement, LinearMesh, LinearNode, _linear_node_snap_key
from ghost_backend.twod.assembly.separation import segment_distance

def elem(p0, p1, idx=0, nodes=(0,1), normal=None):
    p0=np.asarray(p0,float); p1=np.asarray(p1,float)
    L=float(np.linalg.norm(p1-p0)); t=(p1-p0)/L
    n=np.array([t[1],-t[0]]) if normal is None else np.asarray(normal,float)
    return LinearElement('e',2,0,0,0,tuple(nodes),p0,p1,0.5*(p0+p1),t,n,L,idx)

def mesh_from(segs):
    """segs: list of (p0,p1). nodes merged by snap key."""
    nodes=[]; keymap={}; els=[]
    for i,(a,b) in enumerate(segs):
        ids=[]
        for p in (a,b):
            p=np.asarray(p,float); key=_linear_node_snap_key(p)
            if key not in keymap:
                keymap[key]=len(nodes); nodes.append(LinearNode(p,key))
            ids.append(keymap[key])
        els.append(elem(a,b,i,ids))
    return LinearMesh(nodes,els)

_gl={}
def gl(n):
    if n not in _gl:
        x,w=np.polynomial.legendre.leggauss(n); _gl[n]=((x+1)/2,w/2)
    return _gl[n]

def kern(k, r):
    z=complex(k)*r; ph=np.exp(-1j*z)
    return .25j*hankel2e(0,z)*ph, .25j*complex(k)*hankel2e(1,z)*ph

def ref_pair(o, s, k, order=24, maxdepth=120, c=1.0):
    """Reference S, K' (obs normal), K (src normal) 2x2 blocks for a non-self pair
    by geometric hp-refinement (independent of the code's rules)."""
    t,w=gl(order)
    boxes=np.array([[0.,1.,0.,1.]])
    S=np.zeros((2,2),complex); Kp=np.zeros((2,2),complex); K=np.zeros((2,2),complex)
    so=o.p1-o.p0; ss=s.p1-s.p0
    for depth in range(maxdepth):
        if not len(boxes): break
        oa,ob,sa,sb=boxes.T
        A0=o.p0+oa[:,None]*so; A1=o.p0+ob[:,None]*so; B0=s.p0+sa[:,None]*ss; B1=s.p0+sb[:,None]*ss
        d=segment_distance(A0,A1,B0,B1)
        lo=(ob-oa)*o.length; ls=(sb-sa)*s.length
        size=np.maximum(lo,ls)
        ok=(size<=c*d)&(abs(k)*size<=2.0)
        accall=boxes[ok]
        for c0 in range(0,len(accall),400):
            acc=accall[c0:c0+400]
            a0,a1,b0,b1=acc.T
            xo=a0[:,None]+(a1-a0)[:,None]*t; xs=b0[:,None]+(b1-b0)[:,None]*t
            P=o.p0[None,None,:]+xo[:,:,None]*so; Q=s.p0[None,None,:]+xs[:,:,None]*ss
            diff=P[:,:,None,:]-Q[:,None,:,:]
            r=np.linalg.norm(diff,axis=3)
            g,dg=kern(k,r)
            W=(w[:,None]*w[None,:])[None]*((a1-a0)*(b1-b0)*o.length*s.length)[:,None,None]
            po=np.stack((1-xo,xo),-1); ps=np.stack((1-xs,xs),-1)
            S+=np.einsum('nij,nia,njb->ab',W*g,po,ps)
            Kp+=np.einsum('nij,nia,njb->ab',W*(-dg*(diff@o.normal)/r),po,ps)
            K+=np.einsum('nij,nia,njb->ab',W*(dg*(diff@s.normal)/r),po,ps)
        if len(boxes)>400000: raise MemoryError('too many boxes')
        rest=boxes[~ok]; lo=lo[~ok]; ls=ls[~ok]
        if not len(rest): boxes=rest; break
        oa,ob,sa,sb=rest.T; om=.5*(oa+ob); sm=.5*(sa+sb)
        splito=lo>=ls*0.999; splits=ls>=lo*0.999
        new=[]
        both=splito&splits
        for m,(xa,xb,ya,yb) in ((both,(oa,om,sa,sm)),(both,(oa,om,sm,sb)),(both,(om,ob,sa,sm)),(both,(om,ob,sm,sb)),
                                (splito&~splits,(oa,om,sa,sb)),(splito&~splits,(om,ob,sa,sb)),
                                (splits&~splito,(oa,ob,sa,sm)),(splits&~splito,(oa,ob,sm,sb))):
            if m.any(): new.append(np.column_stack((xa[m],xb[m],ya[m],yb[m])))
        boxes=np.concatenate(new)
    return S,Kp,K

def ref_self(L, k, dps=30):
    """Self S block: L^2 (j/4) int_0^1 H0(kLu) C_ij(u) du (mpmath)."""
    mp.mp.dps=dps
    kk=mp.mpc(complex(k).real,complex(k).imag)
    def f(u,c):
        return mp.hankel2(0,kk*L*u)*c(u)
    cd=lambda u:(2-3*u+u**3)/3; co=lambda u:(1-u**3)/3
    n=max(4,int(abs(k)*L/2)+2)
    pts=[mp.mpf(i)/n for i in range(n+1)]
    d=mp.quad(lambda u:f(u,cd),pts); off=mp.quad(lambda u:f(u,co),pts)
    f=0.25j*L*L
    return f*np.array([[complex(d),complex(off)],[complex(off),complex(d)]])

def relerr(a,b):
    return float(np.max(np.abs(a-b))/max(np.max(np.abs(b)),1e-300))
