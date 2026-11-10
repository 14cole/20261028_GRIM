from ref import *
import ghost_backend.twod.operators as ops
from ghost_backend.twod.assembly.separation import requires_adaptive
import warnings, sys, functools; warnings.simplefilter('ignore')
print=functools.partial(print,flush=True)
rng=np.random.RandomState(11); h=0.01
worst={}
cnt=0
for k in (30.0, 150.0, 100-60j):
    wS=wK=0; arg=None
    for trial in range(4000):
        if cnt>=260: break
        lr=rng.choice([1.0,1.0,0.5,0.1,0.02]); a1,a2,dr=rng.uniform(0,2*np.pi,3); rr=rng.uniform(0.3,1.6)*h
        a=0.5*h*np.array([np.cos(a1),np.sin(a1)]); c=rr*np.array([np.cos(dr),np.sin(dr)]); b=0.5*lr*h*np.array([np.cos(a2),np.sin(a2)])
        o=elem(-a,a,0,(0,1)); s=elem(c-b,c+b,1,(2,3))
        if requires_adaptive(o,s): continue
        if float(segment_distance(o.p0,o.p1,s.p0,s.p1))<=0: continue
        cnt+=1
        R=ref_pair(o,s,k,maxdepth=40)
        S,Kp=ops._integrate_linear_pairs_box_sk_batched([o,s],np.array([0]),np.array([1]),k,True,16)
        S,Kp=S[0],Kp[0]
        # K scale: integral of |kernel| ~ LL'/(2 pi gap)
        gap=float(segment_distance(o.p0,o.p1,s.p0,s.p1))
        eS=relerr(S,R[0]); eK=np.max(abs(Kp-R[1]))/(o.length*s.length/(2*np.pi*gap))
        if eK>wK: wK=eK; arg=(lr,rr/h,gap/h)
        wS=max(wS,eS)
    print(f"k={k}: fixed 16-pt class ({cnt} random non-adaptive pairs so far): worst S rel {wS:.1e}, worst K' err/(LL'/(2pi gap)) {wK:.1e} at (len ratio, centre/h, gap/h)={arg}")
    cnt=0
