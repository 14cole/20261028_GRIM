from asm import *
from ghost_backend.twod.assembly.profiling import profile_scope
from ghost_backend.twod.assembly.scatter import SystemScatter
import ghost_backend.twod.assembly.near_store as ns
import sys
N=int(sys.argv[1]); mesh=circle_mesh(N,a=0.5)
k=0.31/mesh.elements[0].length
n=len(mesh.nodes); ids=np.arange(n)
def run(order,floor_patch,store_bytes=None):
    M=[np.zeros((n,n),complex,order='F') for _ in range(4)]
    orig=ops._graded_w_far_floor; ob=ns.NEAR_STORAGE_BYTES
    if floor_patch: ops._graded_w_far_floor=lambda *a,**kw:2
    if store_bytes is not None: ns.NEAR_STORAGE_BYTES=store_bytes
    st=cpu.CPUState(kernel_only=True); st.reuse_operators=False
    try:
        with cpu._STATE.override(st), profile_scope() as prof:
            t=time.perf_counter()
            ops._assemble_multi(mesh,k,True,[None],obs_order=order,src_order=order,output_node_ids_many=[(ids,ids)],
                operator_outputs=[(MatrixDestination(M[0],n),MatrixDestination(M[1],n))],
                additional_operator_outputs=[(MatrixDestination(M[2],n),MatrixDestination(M[3],n))])
            dt=time.perf_counter()-t
    finally:
        ops._graded_w_far_floor=orig; ns.NEAR_STORAGE_BYTES=ob
    return dt,dict(prof.seconds),M
print('N',N,'kL',k*mesh.elements[0].length,'tile',ops._assembly_tile_size(N,16*30+56))
run(8,False)
res={}
for rep in range(2):
    for label,args in (('default q=8 (W floor)',(8,False)),('q=6 uniform far',(6,True)),('default, near store on disk',(8,False,0))):
        dt,sec,M=run(*args)
        res.setdefault(label,[]).append((dt,sec.get('far_integration'),sec.get('near_integration'),sec.get('near_scatter')))
        if label.startswith('default q') and rep==0: base=M
        if label.startswith('q=6') and rep==0:
            print('q=6 vs q=8 matrices: max entry-rel diff', [f"{np.max(abs(a-b))/np.max(abs(b)):.1e}" for a,b in zip(M,base)])
        if 'disk' in label and rep==0:
            print('disk store bitwise equal', all(np.array_equal(a,b) for a,b in zip(M,base)))
for l,v in res.items(): print(l, [tuple(round(x,2) for x in r) for r in v], '(total, far_integration, near_integration, near_scatter) s')
