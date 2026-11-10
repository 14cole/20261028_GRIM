import sys, time, collections, pickle
sys.path.insert(0,'..')
from lib import *
from common import *
from ghost_backend.bor import dispatch as D
from ghost_backend.execution.options import cpu_allocation_scope
from ghost_backend.execution.thread_control import threadpool_limits
n=int(sys.argv[1]); f=float(sys.argv[2])
g=bor_sphere(0.1,n)
rec=collections.Counter(); calls=[]
orig=K._near_rule_moments
def w(kind, stable, points, delta, k, layout, orders, count, start_order=0):
    t=time.thread_time(); r=orig(kind, stable, points, delta, k, layout, orders, count, start_order); dt=time.thread_time()-t
    npt=len(delta); na=int(np.sum(orders))
    rec[(kind,'calls')]+=1; rec[(kind,'points')]+=npt; rec[(kind,'samples')]+=npt*na; rec[(kind,'momentwork')]+=npt*na*count; rec[(kind,'cpu')]+=dt
    if len(calls)<200000: calls.append((kind,stable,npt,int(layout),tuple(int(o) for o in orders),int(count)))
    return r
K._near_rule_moments=w
T=CpuTimers(); T.wrap(K,'_graded_near_kernels')
with cpu_allocation_scope(1), threadpool_limits(1):
    c=time.process_time()
    r=D.solve_monostatic_rcs_bor(g,[f],[0.0,60.0],geometry_units='meters',bor_options={'near_backend':'threads'})
    print('total cpu',time.process_time()-c)
T.report()
for kind in ('g','mfie','ibc'):
    if rec[(kind,'calls')]:
        print(kind,{k[1]:(round(v,2) if isinstance(v,float) else v) for k,v in rec.items() if k[0]==kind},
              'avg pts/call',rec[(kind,'points')]/rec[(kind,'calls')],'avg na',rec[(kind,'samples')]/rec[(kind,'points')],
              'ns/sample',1e9*rec[(kind,'cpu')]/rec[(kind,'samples')],'ns/momentwork',1e9*rec[(kind,'cpu')]/rec[(kind,'momentwork')])
pickle.dump(calls,open(f'nearcalls_{n}.pkl','wb'))
# distribution of points per call
pts=np.array([c[2] for c in calls]); print('pts/call quantiles',np.quantile(pts,[0,.25,.5,.75,.9,1]),'calls',len(pts))
