from asm import *
from ghost_backend.twod.assembly.native import far as nf, table as nt, near as nn
from ghost_backend.twod.assembly.profiling import profile_scope
mesh=circle_mesh(1200,a=0.5); k=0.31/mesh.elements[0].length
def t(label):
    with profile_scope() as prof:
        t0=time.perf_counter(); M=fused(mesh,k,True); dt=time.perf_counter()-t0
    print(label,round(dt,2),{a:round(b,2) for a,b in prof.seconds.items()},[e.get('evaluation_backend') for e in M['events']]); return M
A=t('native libs present   ')
# simulate a checkout where the .so files were never built
nt.library.cache_clear(); nf.library.cache_clear(); nf.tile_library.cache_clear(); nf.scatter_library.cache_clear()
o1,o2,o3,o4=nt.library,nf.library,nf.tile_library,nf.scatter_library
nt.library=lambda:None; nf.library=lambda:None; nf.tile_library=lambda:None; nf.scatter_library=lambda:None; nn.ENABLED=False
B=t('native libs unavailable')
print('max rel diff native vs python fallback:',{x:f"{np.max(abs(A[x]-B[x]))/np.max(abs(A[x])):.1e}" for x in 'SKDW'})
