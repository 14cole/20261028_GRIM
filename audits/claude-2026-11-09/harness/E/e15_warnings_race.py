import sys, os, time, threading, warnings
sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
import numpy as np
from ghost_backend.linalg import hierarchical as H
from e5_lib import kernel, circle
n=1024; w=2*np.pi/n; xy=circle(n); A=kernel(xy,20.,w)+0.5*np.eye(n)
H.LEAF_SIZE=16   # many leaf LUs -> many catch_warnings windows (does not change the pattern under test)
filters0=list(warnings.filters)
stop=threading.Event(); raised=[]; emitted=[0]
def victim():
    # another thread doing ordinary numerics that emits a benign RuntimeWarning (as assembly code can)
    a=np.array([1.0,0.0])
    while not stop.is_set():
        try:
            with np.errstate(divide='warn'):
                np.divide(1.0,a)      # RuntimeWarning: divide by zero
            emitted[0]+=1
        except RuntimeWarning as e:
            raised.append(str(e))
def builder():
    for _ in range(6):
        H.HierarchicalFactor(A,xy)
ths=[threading.Thread(target=builder) for _ in range(3)]
v=threading.Thread(target=victim); 
warnings.simplefilter('always')   # make the victim's warning recur (default filter would show once)
filters0=list(warnings.filters)
v.start(); [t.start() for t in ths]; [t.join() for t in ths]; stop.set(); v.join()
print('victim warnings emitted',emitted[0],'-> turned into EXCEPTIONS in the victim thread:',len(raised))
print('warnings.filters restored after all builders finished:',list(warnings.filters)==filters0,'| leading filter now:',warnings.filters[0][:1], 'before:',filters0[0][:1])
