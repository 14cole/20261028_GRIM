"""Two overlapping in-process compressed solves in threads (1280 unknowns each, tiny vs RAM)."""
import sys, os, time, threading
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp')
from lib import *
from ghost_backend.twod import solver as S
g=circle_geo(0.5,256,props='2 0 0 0 0')
opts=dict(factorization=sys.argv[1], mesh_strategy='global', assembly_threads=1, blas_threads=1)
res={}
def solve(name, f, delay):
    time.sleep(delay)
    try:
        t=time.time(); r=S.solve_monostatic_rcs_2d(g,[f],[0.,30.],geometry_units='meters',solver_method='auto',execution_options=opts)
        ma=r['metadata']['memory_accounting']; res[name]=('ok',round(time.time()-t,2), 'shared',ma['shared_process'],'checks',ma['total_checks'])
    except BaseException as e: res[name]=('ERR',type(e).__name__,str(e)[:600])
ts=[threading.Thread(target=solve,args=('A',6.0,0)),threading.Thread(target=solve,args=('B',6.06,float(sys.argv[2])))]
[t.start() for t in ts]; [t.join() for t in ts]
for k in sorted(res): print(k,res[k])
