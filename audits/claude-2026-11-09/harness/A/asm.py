from ref import *
import ghost_backend.twod.operators as ops
from ghost_backend.execution import cpu
from ghost_backend.twod.assembly.scatter import MatrixDestination
import time
def circle_mesh(N, a=0.5, jitter=0.0, seed=0):
    rng=np.random.RandomState(seed)
    th=np.linspace(0,2*np.pi,N+1)[:-1]
    if jitter: th=th+jitter*(2*np.pi/N)*rng.uniform(-.5,.5,N)
    th=-th  # clockwise
    P=a*np.column_stack((np.cos(th),np.sin(th)))
    return mesh_from([(P[i],P[(i+1)%N]) for i in range(N)])
def fused(mesh,k,state=True,want=('S','K','D','W'),threads=1):
    n=len(mesh.nodes); ids=np.arange(n)
    M={x:np.zeros((n,n),complex,order='F') for x in want}
    from ghost_backend.twod.assembly.scatter import SystemScatter
    empty=np.empty(0,np.int64)
    def dest(x):
        return MatrixDestination(M[x],n) if x in M else SystemScatter(np.zeros((0,0),complex),n,empty,empty,[])
    def run():
        ops.set_assembly_threads(threads)
        ops._assemble_multi(mesh,k,True,[None],compute_single_layer='S' in want,compute_double_layer='K' in want,
            output_node_ids_many=[(ids if 'S' in want else empty,ids)],
            double_layer_output_node_ids_many=[(ids if 'K' in want else empty,ids)],
            operator_outputs=[(dest('S'),dest('K'))],
            additional_operator_outputs=[(dest('D'),dest('W'))] if ('D' in want or 'W' in want) else None)
    if state:
        st=cpu.CPUState(kernel_only=True); st.reuse_operators=False
        with cpu._STATE.override(st): run()
        M['events']=st.table_events
    else: run()
    return M
