"""Two overlapping in-process solves (threads): does the second get any reservation?"""
import sys, os, time, threading, traceback
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp')
from lib import *
from ghost_backend.twod import solver as S
from ghost_backend.execution import memory_budget as MB
g=circle_geo(0.1,64,props='2 0 0 0 0')
# (1) direct ledger test
out={}
def req(name, hold, go):
    try:
        with MB.scope() as st:
            lim=st.limit()
            out[name]=dict(limit=lim, stable=st.last['stable_reservation_gib'], binding=st.last['binding_constraint'], res=st.last['reservation_binding_constraint'], shared=st.shared_process, constraints=st.last['reservation_constraints_gib'])
            go.set(); hold.wait(5)
    except Exception as e: out[name]=repr(e); go.set()
h=threading.Event(); g1=threading.Event(); g2=threading.Event()
t1=threading.Thread(target=req,args=('first',h,g1)); t1.start(); g1.wait()
t2=threading.Thread(target=req,args=('second',h,g2)); t2.start(); g2.wait(); h.set(); t1.join(); t2.join()
for k,v in out.items(): print(k, v)
# (2) real solves overlapping
res={}
def solve(name, f):
    try:
        t=time.time(); r=S.solve_monostatic_rcs_2d(g,[f],[0.,30.],geometry_units='meters',solver_method='auto'); res[name]=('ok',round(time.time()-t,2), r['metadata']['memory_accounting']['shared_process'])
    except BaseException as e: res[name]=('ERR',type(e).__name__,str(e)[:400])
ts=[threading.Thread(target=solve,args=('A',3.0)),threading.Thread(target=solve,args=('B',3.1))]
[t.start() for t in ts]; [t.join() for t in ts]
print(res)
