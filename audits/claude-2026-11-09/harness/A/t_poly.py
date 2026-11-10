from ref import *
import ghost_backend.twod.operators as ops
import ghost_backend.twod.polynomial_quadrature as pq
from ghost_backend.twod.basis import coefficients
import warnings, sys, functools; warnings.simplefilter('ignore')
print=functools.partial(print,flush=True)
def ref_moments(o,s,k,order=26,maxdepth=90):
    t,w=gl(order); boxes=np.array([[0.,1.,0.,1.]])
    MS=np.zeros((4,4),complex); MK=np.zeros((4,4),complex); so=o.p1-o.p0; ss=s.p1-s.p0
    for depth in range(maxdepth):
        if not len(boxes): break
        oa,ob,sa,sb=boxes.T
        d=segment_distance(o.p0+oa[:,None]*so,o.p0+ob[:,None]*so,s.p0+sa[:,None]*ss,s.p0+sb[:,None]*ss)
        lo=(ob-oa)*o.length; ls=(sb-sa)*s.length; size=np.maximum(lo,ls)
        ok=(size<=d)&(abs(k)*size<=2.0)
        for c0 in range(0,int(ok.sum()),300):
            a0,a1,b0,b1=boxes[ok][c0:c0+300].T
            xo=a0[:,None]+(a1-a0)[:,None]*t; xs=b0[:,None]+(b1-b0)[:,None]*t
            diff=(o.p0+xo[:,:,None]*so)[:,:,None,:]-(s.p0+xs[:,:,None]*ss)[:,None,:,:]
            r=np.linalg.norm(diff,axis=3); g,dg=kern(k,r)
            W=(w[:,None]*w[None,:])[None]*((a1-a0)*(b1-b0)*o.length*s.length)[:,None,None]
            po=xo[:,:,None]**np.arange(4); ps=xs[:,:,None]**np.arange(4)
            MS+=np.einsum('nij,nia,njb->ab',W*g,po,ps); MK+=np.einsum('nij,nia,njb->ab',W*(-dg*(diff@o.normal)/r),po,ps)
        rest=boxes[~ok]; lo=lo[~ok]; ls=ls[~ok]
        if not len(rest): break
        oa,ob,sa,sb=rest.T; om=.5*(oa+ob); sm=.5*(sa+sb); so_=lo>=ls
        boxes=np.concatenate([np.column_stack((oa,np.where(so_,om,ob),sa,np.where(so_,sb,sm))),np.column_stack((np.where(so_,om,oa),ob,np.where(so_,sa,sm),sb))])
    return MS,MK
def ref_self_moments(L,k,dps=30):
    mp.mp.dps=dps; kk=mp.mpc(complex(k).real,complex(k).imag)
    M=np.zeros((4,4),complex)
    n=max(4,int(abs(k)*L/2)+2); pts=[mp.mpf(i)/n for i in range(n+1)]
    def half(a,b,u): return sum(mp.binomial(b,j)*u**(b-j)*(1-u)**(a+j+1)/(a+j+1) for j in range(b+1))
    for a in range(4):
        for b in range(a,4):
            v=mp.quad(lambda u: mp.hankel2(0,kk*L*u)*(half(a,b,u)+half(b,a,u)),pts)
            M[a,b]=M[b,a]=0.25j*L*L*complex(v)
    return M
def pelem(p0,p1,idx,deg,base):
    e=elem(p0,p1,idx,tuple(range(base,base+deg+1))); return e
h=0.01
for deg in (2,3):
    C=coefficients(deg)
    for k in [complex(a) for a in sys.argv[1:]]:
        k=k.real if k.imag==0 else k
        e=pelem((0,0),(h,0),0,deg,0)
        S=pq.near_block(e,e,k,True)[0]; Sb=pq.near_blocks([(e,e)],k,True)[0][0]
        R=C.T@ref_self_moments(h,k)[:deg+1,:deg+1]@C
        out=[f"self {relerr(S,R):.1e} (batched {relerr(Sb,R):.1e})"]
        for name,q0,q1,nodes in (('touch90',(h,0),(h,h),None),('touch170',(h,0),(h+h*math.cos(math.radians(10)),h*math.sin(math.radians(10))),None),
                                 ('touch8deg r3',(h,0),(h-3*h*math.cos(math.radians(8)),3*h*math.sin(math.radians(8))),None),
                                 ('gap .3h',(0.1*h,0.3*h),(1.4*h,0.5*h),10),('thin gap .02h',(0.1*h,0.02*h),(1.4*h,0.02*h),10),('ratio2.9',(0,2.9*h),(h,2.9*h),10)):
            s=pelem(q0,q1,1,deg,10)
            if nodes is None: s.node_ids=(1,)+tuple(range(10,10+deg))   # share endpoint node 1 of obs (its p1)
            try:
                Sc,Kc=pq.near_block(e,s,k,True); Sb,Kb=pq.near_blocks([(e,s)],k,True)[0]
                MS,MK=ref_moments(e,s,k); RS=C.T@MS[:deg+1,:deg+1]@C; RK=C.T@MK[:deg+1,:deg+1]@C
                sc=np.max(abs(RK)) if np.max(abs(RK))>0 else 1
                out.append(f"{name} S {relerr(Sc,RS):.1e}/{relerr(Sb,RS):.1e} K' {np.max(abs(Kc-RK))/sc:.1e}/{np.max(abs(Kb-RK))/sc:.1e}")
            except Exception as ex: out.append(f"{name} EXC {str(ex)[:80]}")
        print(f"deg {deg} k={k} |k|h={abs(k)*h:.2f}: "+"; ".join(out))
