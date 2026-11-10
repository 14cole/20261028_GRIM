from lib import *
import threading
from ghost_backend.twod import solver as S
g=circle_geo(0.1,68); out=[]
def run(i):
    try: S.solve_monostatic_rcs_2d(g,[1.0],[0.0],geometry_units='meters',solver_method='direct'); out.append((i,'ok'))
    except Exception as e: out.append((i,type(e).__name__,str(e)[:230]))
ts=[threading.Thread(target=run,args=(i,)) for i in range(3)]
[t.start() for t in ts]; [t.join() for t in ts]; print(out)
