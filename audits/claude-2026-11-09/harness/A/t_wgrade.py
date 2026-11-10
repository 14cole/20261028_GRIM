from asm import *
import warnings, functools; warnings.simplefilter('ignore')
print=functools.partial(print,flush=True)
N=240; a=0.3
mesh=circle_mesh(N,a=a,jitter=0.5,seed=4)
n=len(mesh.nodes); h=2*np.pi*a/N
X=np.array([nd.xy for nd in mesh.nodes]); dist=np.linalg.norm(X[:,None]-X[None],axis=2)/ (max(e.length for e in mesh.elements))
def W(k,q):
    M=np.zeros((n,n),complex,order='F')
    ops._assemble_linear_hypersingular_matrix(mesh,k,obs_order=q,src_order=q,destination=M)
    return M
orig=ops._graded_w_far_floor
for kL in (0.31,1.0,1.5):
    k=kL/max(e.length for e in mesh.elements)
    ref=W(k,16)
    ops._graded_w_far_floor=lambda *a,**kw:2
    row=[]
    for q in (5,6,7,8):
        Wq=W(k,q)
        rel=abs(Wq-ref)/np.maximum(abs(ref),1e-300)
        relrow=abs(Wq-ref)/np.max(abs(ref),axis=1,keepdims=True)
        row.append(f"q={q}: entry-rel err [node-dist/Lmax 4-6: {rel[(dist>4)&(dist<6)].max():.1e}, 6-11: {rel[(dist>=6)&(dist<11)].max():.1e}, >=11: {rel[dist>=11].max():.1e}] rel-to-diag {np.max(abs(Wq-ref))/np.max(abs(ref)):.1e}")
    ops._graded_w_far_floor=orig
    print(f"kL={kL}:\n   "+"\n   ".join(row))
