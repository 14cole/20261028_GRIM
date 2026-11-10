import os,sys
os.environ['OMP_NUM_THREADS']='1'; os.environ['OPENBLAS_NUM_THREADS']='1'
sys.path.insert(0,'..')
from lib import *
import cProfile,pstats,io,time
from ghost_backend.twod import solver as S
N=int(sys.argv[1]); a=0.5
g=circle_geo(a,N)
f=float(sys.argv[2]) if len(sys.argv)>2 else 1.0
t=time.time()
pr=cProfile.Profile(); pr.enable()
r=S.solve_monostatic_rcs_2d(g,[f],[0.0,37.0],geometry_units='meters')
pr.disable()
print('total',time.time()-t)
md=r.get('metadata',{})
print({k:v for k,v in md.items() if k in('assembly_components','solver_method','stage_seconds','timings')})
for k in ('frequency_metadata',):
    if k in md:
        m=md[k][0]['metadata'] if isinstance(md[k],list) else md[k]
        print({kk:vv for kk,vv in m.items() if 'time' in kk or 'second' in kk or 'stage' in kk or 'assembly' in kk})
s=io.StringIO(); pstats.Stats(pr,stream=s).sort_stats('cumulative').print_stats(45); print(s.getvalue()[:9000])
s=io.StringIO(); pstats.Stats(pr,stream=s).sort_stats('tottime').print_stats(25); print(s.getvalue()[:5000])
