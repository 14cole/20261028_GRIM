from asm import *
import cProfile,pstats,io,sys
from ghost_backend.twod.assembly.profiling import profile_scope
N=int(sys.argv[1]); k=float(sys.argv[2]); state=int(sys.argv[3]); want=tuple(sys.argv[4])
mesh=circle_mesh(N)
print('N',N,'kh',k*mesh.elements[0].length,'state',state,want)
fused(circle_mesh(64),k,state,want)  # warm
pr=cProfile.Profile()
with profile_scope() as prof:
    t=time.time(); pr.enable(); M=fused(mesh,k,state,want); pr.disable(); dt=time.time()-t
print('seconds',dt, {a:round(b,2) for a,b in prof.seconds.items()})
if state: print([ (e.get('used'),e.get('intervals'),e.get('evaluation_backend'),round(e.get('build_seconds',0),3)) for e in M['events']])
s=io.StringIO(); pstats.Stats(pr,stream=s).sort_stats('tottime').print_stats(22); print(s.getvalue()[:4500])
import resource; print('maxrss MB',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
