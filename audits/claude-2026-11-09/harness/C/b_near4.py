import sys, pickle, ctypes
from common import *
saved=pickle.load(open(sys.argv[1],'rb'))
def run(lib):
    S._NATIVE=ctypes.CDLL(lib) if lib else S._NATIVE
    out=[]; cpu={'g':0,'mfie':0}
    for rep in range(3):
        o=[]
        for (kind,stable,points,delta,k,layout,orders,count) in saved:
            t=time.thread_time(); r=K._near_rule_moments(kind,stable,points,delta,k,layout,orders,count); dt=time.thread_time()-t
            if rep: cpu[kind]+=dt/2
            o.append(r if kind=='g' else np.concatenate(r,axis=1))
        out=o
    return out,cpu
import os
which=sys.argv[2]
out,cpu=run(os.path.abspath(which))
pickle.dump(out,open(which+'.res','wb')); print(which,{k:round(v,3) for k,v in cpu.items()})
