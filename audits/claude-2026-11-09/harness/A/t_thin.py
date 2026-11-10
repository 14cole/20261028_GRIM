from asm import *
from ghost_backend.twod.assembly.profiling import profile_scope
import cProfile,pstats,io,sys
N=int(sys.argv[1]); gapf=float(sys.argv[2]); a=0.5
h=2*np.pi*a/N
def ring(r,off):
    th=-(np.linspace(0,2*np.pi,N+1)[:-1]+off*2*np.pi/N); P=r*np.column_stack((np.cos(th),np.sin(th)))
    return [(P[i],P[(i+1)%N]) for i in range(N)]
mesh=mesh_from(ring(a,0.0)+ring(a+gapf*h,0.37))
k=0.31/h
print('elements',len(mesh.elements),'gap/h',gapf)
fused(circle_mesh(64),k,True)
pr=cProfile.Profile()
with profile_scope() as prof:
    t=time.time(); pr.enable(); M=fused(mesh,k,True,('S','K')); pr.disable(); dt=time.time()-t
print('seconds',round(dt,2),{a:round(b,2) for a,b in prof.seconds.items()})
s=io.StringIO(); pstats.Stats(pr,stream=s).sort_stats('tottime').print_stats(16); print(s.getvalue()[s.getvalue().index('ncalls'):][:3300])
s=io.StringIO(); pstats.Stats(pr,stream=s).sort_stats('cumulative').print_stats('operators.py|thin_gap|near.py|separation',14); print(s.getvalue()[s.getvalue().index('ncalls'):][:3000])
