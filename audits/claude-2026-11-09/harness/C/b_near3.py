import sys, pickle
from common import *
saved=pickle.load(open(sys.argv[1],'rb'))
orig=K._near_rule_moments
def val(kind,res):
    if kind=='g': return res
    return np.concatenate(res,axis=1)
def scaled(orders, s, layout):
    o=np.maximum(2,np.ceil(np.asarray(orders)*s)).astype(np.int64)
    return o
tot=collections=None
import collections
errs=collections.defaultdict(list); cpu=collections.Counter(); work=collections.Counter()
fine_levels=0
for (kind,stable,points,delta,k,layout,orders,count) in saved:
    ref=val(kind,orig(kind,stable,points,delta,k,layout,scaled(orders,3.0,layout),count))
    sc=np.max(np.abs(ref),axis=(1,2)) if kind=='g' else np.max(np.abs(ref),axis=(1,2))
    for s in (0.5,0.67,0.8,1.0,1.5):
        t=time.thread_time(); v=val(kind,orig(kind,stable,points,delta,k,layout,scaled(orders,s,layout),count)); dt=time.thread_time()-t
        e=np.max(np.abs(v-ref),axis=(1,2))/sc
        errs[(kind,s)].append(e); cpu[(kind,s)]+=dt
    # split: sampling-only cost (count=1)
    t=time.thread_time(); orig(kind,stable,points,delta,k,layout,orders,1); cpu[(kind,'count1')]+=time.thread_time()-t
    t=time.thread_time(); orig(kind,stable,points,delta,k,layout,orders,count); cpu[(kind,'full')]+=time.thread_time()-t
print('NOTE saved orders are a mix of coarse- and fine-level calls; scale s is relative to the recorded call')
for kind in ('g','mfie'):
    for s in (0.5,0.67,0.8,1.0,1.5):
        e=np.concatenate(errs[(kind,s)])
        print(kind,'scale',s,'max err %.1e  99.9%% %.1e median %.1e  cpu %.2f'%(e.max(),np.quantile(e,.999),np.median(e),cpu[(kind,s)]))
    print(kind,'cpu count=1 (sampling+nodes only)',round(cpu[(kind,'count1')],3),'full',round(cpu[(kind,'full')],3))
