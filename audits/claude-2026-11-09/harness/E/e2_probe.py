import sys, os, json, time
sys.path.insert(0,'..'); from lib import *
from ghost_backend.twod import solver as S
g = circle_geo(0.1, 240)
t=time.time()
r = S.solve_monostatic_rcs_2d(g, [3.0], [0.0, 37.0], geometry_units='meters', compute_condition_number=True,
     execution_options=dict(factorization=sys.argv[1], mesh_strategy='global', assembly_threads=2, blas_threads=2))
print('t',time.time()-t)
print(list(r.keys()))
print(r['samples'][0])
md=r['metadata']
def show(d,ind=0,depth=0):
    for k,v in d.items():
        if isinstance(v,dict) and depth<2: print(' '*ind+k+':'); show(v,ind+2,depth+1)
        else: print(' '*ind+k+':',str(v)[:300])
show(md)
