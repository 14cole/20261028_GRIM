import sys, os, time, threading, numpy as np
sys.path.insert(0, '/home/user/20261028_GRIM/tools/GHOST')
import ghost_backend.bor.kernels as K
import ghost_backend.bor.streaming as S
from ghost_backend.bor.solver import BorPecSolver
def sphere_pts(a,n):
    th=np.linspace(0,np.pi,n+1); r=a*np.sin(th); z=a*np.cos(th); r[0]=r[-1]=0
    return np.column_stack([r,z])
def cyl_pts(a,h,n):
    # capped cylinder generatrix, ~n elements
    per=a+h+a; n1=max(2,int(round(n*a/per))); n2=max(2,n-2*n1)
    p=[(x,h/2) for x in np.linspace(0,a,n1+1)]+[(a,z) for z in np.linspace(h/2,-h/2,n2+1)[1:]]+[(x,-h/2) for x in np.linspace(a,0,n1+1)[1:]]
    return np.array(p)
class CpuTimers:
    def __init__(self): self.t={}; self.c={}; self.lock=threading.Lock()
    def wrap(self, obj, name, label=None):
        f=getattr(obj,name); label=label or name; T=self
        def w(*a,**k):
            t=time.thread_time()
            try: return f(*a,**k)
            finally:
                dt=time.thread_time()-t
                with T.lock:
                    T.t[label]=T.t.get(label,0)+dt; T.c[label]=T.c.get(label,0)+1
        setattr(obj,name,w); return f
    def report(self):
        for k,v in sorted(self.t.items(), key=lambda x:-x[1]): print(f'  {k:32s} cpu {v:8.2f}s calls {self.c[k]}')
