import os,sys,time
from lib import *
from ghost_backend.twod import solver as S
n=int(sys.argv[1]); meth=sys.argv[2]
g=circle_geo(0.1,n)
t=time.time(); c=time.process_time()
r=S.solve_monostatic_rcs_2d(g,[1.0],[float(a) for a in range(0,61)],geometry_units='meters',solver_method=meth)
print(n,meth,'OPENBLAS',os.environ.get('OPENBLAS_NUM_THREADS'),'wall',round(time.time()-t,2),'cpu',round(time.process_time()-c,2), r['samples'][0]['rcs_db'])
