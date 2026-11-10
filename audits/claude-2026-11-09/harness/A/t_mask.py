from asm import *
from ghost_backend.twod.assembly.compact import CompactOperator
import warnings, functools; warnings.simplefilter('ignore')
print=functools.partial(print,flush=True)
N=64; mesh=circle_mesh(N,a=0.1,jitter=0.8,seed=7); n=len(mesh.nodes); els=mesh.elements
rng=np.random.RandomState(3)
t,w=gl(14)
def blocks(o,s,k):
    c=np.linalg.norm(o.center-s.center)/max(o.length,s.length)
    if o.panel_index==s.panel_index or c<3.0 or set(o.node_ids)&set(s.node_ids):
        S,Kp=ops._sk_blocks_near_linear(o,s,k,True); _,Kd=ops._sk_blocks_near_linear(o,s,k,False)
        return S,Kp,Kd
    P=o.p0+t[:,None]*(o.p1-o.p0); Q=s.p0+t[:,None]*(s.p1-s.p0); diff=P[:,None,:]-Q[None,:,:]; r=np.linalg.norm(diff,axis=2)
    g,dg=kern(k,r); W=np.outer(w,w)*o.length*s.length; ph=np.column_stack((1-t,t))
    return ph.T@(W*g)@ph, ph.T@(W*(-dg*(diff@o.normal)/r))@ph, ph.T@(W*(dg*(diff@s.normal)/r))@ph
T=np.array([[1,-1],[-1,1]])
for k in (50.0,45-20j):
    B={(i,j):blocks(els[i],els[j],k) for i in range(N) for j in range(N)}
    masks=[rng.rand(N)<0.5, rng.rand(N)<0.3, None]
    coeffs=[rng.randn(N)+1j*rng.randn(N), None, None]
    rowsets=[np.sort(rng.choice(n,40,replace=False)), np.arange(n), np.sort(rng.choice(n,25,replace=False))]
    colsets=[np.arange(n), np.sort(rng.choice(n,45,replace=False)), np.arange(n)]
    for tile,state,thr in ((0,0,1),(7,1,1),(7,1,3),(7,0,2)):
        ops._ASSEMBLY_TILE=tile; ops.set_assembly_threads(thr)
        outs=[(CompactOperator(n,r,c),CompactOperator(n,r,c)) for r,c in zip(rowsets,colsets)]
        extra=[(CompactOperator(n,r,c),CompactOperator(n,r,c)) for r,c in zip(rowsets,colsets)]
        def run():
            ops._assemble_multi(mesh,k,True,masks,single_layer_observation_coefficients_many=coeffs,
                output_node_ids_many=list(zip(rowsets,colsets)),operator_outputs=outs,additional_operator_outputs=extra)
        if state:
            st=cpu.CPUState(kernel_only=True); st.reuse_operators=False
            with cpu._STATE.override(st): run()
        else: run()
        ops._ASSEMBLY_TILE=0; ops.set_assembly_threads(1)
        errs=[]
        for mi,(mask,cf,rows,cols) in enumerate(zip(masks,coeffs,rowsets,colsets)):
            R={x:np.zeros((n,n),complex) for x in 'SKDW'}
            for (i,j),(S,Kp,Kd) in B.items():
                if mask is not None and not mask[j]: continue
                ix=np.ix_(els[i].node_ids,els[j].node_ids)
                R['S'][ix]+=S*(1 if cf is None else cf[i]); R['K'][ix]+=Kp; R['D'][ix]+=Kd
                R['W'][ix]+=-complex(k)**2*np.dot(els[i].normal,els[j].normal)*S+T*S.sum()/(els[i].length*els[j].length)
            got=dict(S=outs[mi][0].values,K=outs[mi][1].values,D=extra[mi][0].values,W=extra[mi][1].values)
            errs.append(" ".join(f"{x} {np.max(abs(got[x]-R[x][np.ix_(rows,cols)]))/np.max(abs(R[x])):.0e}" for x in 'SKDW'))
        print(f"k={k} tile={tile} state={state} thr={thr}: "+" | ".join(errs))
