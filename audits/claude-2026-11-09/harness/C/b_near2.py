import sys, time, collections, pickle
sys.path.insert(0,'..')
from lib import *
from common import *
from ghost_backend.bor import dispatch as D
from ghost_backend.execution.options import cpu_allocation_scope
from ghost_backend.execution.thread_control import threadpool_limits
n=int(sys.argv[1]); f=float(sys.argv[2])
g=bor_sphere(0.1,n)
saved=[]; cnt=[0]
orig=K._near_rule_moments
def w(kind, stable, points, delta, k, layout, orders, count, start_order=0):
    cnt[0]+=1
    if cnt[0]%7==0: saved.append((kind,stable,tuple(np.array(p) for p in points),np.array(delta),complex(k),int(layout),np.array(orders),int(count)))
    return orig(kind, stable, points, delta, k, layout, orders, count, start_order)
K._near_rule_moments=w
with cpu_allocation_scope(1), threadpool_limits(1):
    r=D.solve_monostatic_rcs_bor(g,[f],[0.0,60.0],geometry_units='meters',bor_options={'near_backend':'threads'})
pickle.dump(saved,open(f'nearargs_{n}.pkl','wb')); print(len(saved),'of',cnt[0])
