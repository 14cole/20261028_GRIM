"""Two overlapping default-API solves from two threads of one process (no execution_options): second request's RAM reservation."""
import sys, os, time, threading
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp')
from lib import *
from ghost_backend.twod import solver as S
import psutil
g=circle_geo(0.5,256,props='2 0 0 0 0')
res={}
def solve(name, f, delay, kw):
    time.sleep(delay)
    try:
        t=time.time(); r=S.solve_monostatic_rcs_2d(g,[f],[0.,30.],geometry_units='meters',**kw)
        res[name]=('ok',round(time.time()-t,2), r['metadata'].get('solver_method'))
    except BaseException as e: res[name]=('ERR',type(e).__name__,str(e)[:700])
for label,kw in (('default(direct)',{}),('experimental_cpu',dict(solver_method='experimental_cpu'))):
    res.clear()
    ts=[threading.Thread(target=solve,args=('A',6.0,0,kw)),threading.Thread(target=solve,args=('B',6.06,float(sys.argv[1]),kw))]
    [t.start() for t in ts]; [t.join() for t in ts]
    print(label,'available GiB',round(psutil.virtual_memory().available/2**30,1))
    for k in sorted(res): print('  ',k,res[k])
