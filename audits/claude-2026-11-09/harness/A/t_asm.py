from asm import *
import warnings, sys, functools; warnings.simplefilter('ignore')
print=functools.partial(print,flush=True)
def build(case):
    rng=np.random.RandomState(5)
    if case=='irregular':
        # jittered 28-gon + nearby thin strip pair + a far small cluster
        N=28; th=-(np.linspace(0,2*np.pi,N+1)[:-1]+0.6*(2*np.pi/N)*rng.uniform(-.5,.5,N)); a=0.05
        P=a*np.column_stack((np.cos(th),np.sin(th)))
        segs=[(P[i],P[(i+1)%N]) for i in range(N)]
        x=np.array([0.0,0.004,0.013,0.02,0.031]); 
        segs+=[((0.06+x[i],0.0),(0.06+x[i+1],0.0)) for i in range(4)]
        segs+=[((0.06+x[i],0.0006),(0.06+x[i+1],0.0006)) for i in range(4)]   # thin gap 0.6mm over ~1cm panels
        segs+=[((0.1,0.03),(0.108,0.033)),((0.108,0.033),(0.1081,0.0331))]     # tiny panel next to large
        return mesh_from(segs)
    if case=='far2':
        segs=[((0,0),(0.001,0)),((0.001,0),(0.002,0.0003)),((5.0,1.0),(5.001,1.0)),((5.001,1.0),(5.002,1.0004)),((0.5,0.2),(0.5,0.201)),((0.7,0.2),(0.7004,0.2008))]
        return mesh_from(segs)
def reference(mesh,k):
    n=len(mesh.nodes); S=np.zeros((n,n),complex); Kp=S.copy(); K=S.copy(); W=S.copy()
    T=np.array([[1,-1],[-1,1]])
    for i,o in enumerate(mesh.elements):
        for j,s in enumerate(mesh.elements):
            if i==j:
                b=(ref_self(o.length,k),np.zeros((2,2)),np.zeros((2,2)))
            else:
                b=ref_pair(o,s,k,maxdepth=100)
            ix=np.ix_(o.node_ids,s.node_ids)
            S[ix]+=b[0]; Kp[ix]+=b[1]; K[ix]+=b[2]
            W[ix]+=-complex(k)**2*np.dot(o.normal,s.normal)*b[0]+T*b[0].sum()/(o.length*s.length)
    return dict(S=S,K=Kp,D=K,W=W)
case=sys.argv[1]
mesh=build(case)
print(case,'elements',len(mesh.elements),'nodes',len(mesh.nodes),'lengths',min(e.length for e in mesh.elements),max(e.length for e in mesh.elements))
for k in [complex(a) for a in sys.argv[2:]]:
    k=k.real if k.imag==0 else k
    R=reference(mesh,k)
    base=None
    for label,state,native,thr in (('numpy/no-table',0,True,1),('table+native',1,True,1),('table numpy-far',1,False,1),('table+native 3thr',1,True,3)):
        ops._NATIVE_FAR=native
        M=fused(mesh,k,bool(state),threads=thr)
        ops._NATIVE_FAR=True
        e={x:np.max(abs(M[x]-R[x]))/np.max(abs(R[x])) for x in 'SKDW'}
        # worst entrywise relative error over entries that are not tiny
        ew={x:np.max(abs(M[x]-R[x])/np.maximum(abs(R[x]),1e-3*np.max(abs(R[x])))) for x in 'SKDW'}
        extra=''
        if label=='table+native': base=M
        if label=='table+native 3thr': extra=' bitwise==1thr: '+str(all(np.array_equal(M[x],base[x]) for x in 'SKDW'))
        ev=M.get('events')
        print(f"k={k}: {label:18s} max-norm rel: "+" ".join(f"{x} {e[x]:.1e}" for x in 'SKDW')+" | entrywise: "+" ".join(f"{x} {ew[x]:.1e}" for x in 'SKDW')+extra+(f" tbl={[(v.get('used'),v.get('intervals'),v.get('partial_domain')) for v in ev]}" if ev else ''))
