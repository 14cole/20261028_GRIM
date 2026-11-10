from asm import *
from ghost_backend.twod.assembly.profiling import profile_scope
N=1200; a=0.5
th=-np.linspace(0,2*np.pi,N+1)[:-1]; P=a*np.column_stack((np.cos(th),np.sin(th)))
segs=[(P[i],P[(i+1)%N]) for i in range(N)]
m1=mesh_from(segs)
# split one panel so that a 5e-4-length sliver exists (e.g. hp grading / CAD sliver)
p,q=segs[0]; mid=p+(q-p)*5e-4
m2=mesh_from([(p,mid),(mid,q)]+segs[1:])
k=0.31/m1.elements[0].length
def run(mesh):
    n=len(mesh.nodes); ids=np.arange(n); M=[np.zeros((n,n),complex,order='F') for _ in range(4)]
    st=cpu.CPUState(kernel_only=True); st.reuse_operators=False
    with cpu._STATE.override(st), profile_scope() as prof:
        ops._assemble_multi(mesh,k,True,[None],output_node_ids_many=[(ids,ids)],
            operator_outputs=[(MatrixDestination(M[0],n),MatrixDestination(M[1],n))],
            additional_operator_outputs=[(MatrixDestination(M[2],n),MatrixDestination(M[3],n))])
    return prof.seconds['far_integration']
run(m1)
for rep in range(2):
    print('uniform mesh far_integration s:',round(run(m1),2),'| same mesh + one sliver panel (L/Lmax=5e-4):',round(run(m2),2),
          '| W floor chosen:',ops._graded_w_far_floor(k,np.array([e.length for e in m1.elements]),3.0,1),ops._graded_w_far_floor(k,np.array([e.length for e in m2.elements]),3.0,1))
