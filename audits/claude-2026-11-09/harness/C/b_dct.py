from common import *
from scipy import fft
from ghost_backend.execution.thread_control import threadpool_limits
rng=np.random.default_rng(0)
def cpu(f,reps):
    t=time.thread_time()
    for _ in range(reps): f()
    return (time.thread_time()-t)/reps
with threadpool_limits(1):
  for size,m,p in ((128,58,4000),(160,58,4000),(224,58,2000),(352,58,1000),(512,58,1000),(1184,58,300),(1024,58,300),(1216,58,300),(1312,58,300),(2016,58,200),(2048,58,200),(1888,58,200)):
    h=size//2+1; modes=np.arange(m)
    x=rng.standard_normal((p,h))+1j*rng.standard_normal((p,h))
    cos,_,_,_,_=K._half_grid_tables(size,modes,False,'complex')
    cr,_,_,_,_=K._half_grid_tables(size,modes,False,'real')
    reps=max(2,int(3e7/(p*h*m)))
    a=cpu(lambda: K._project_half_grid(x,cos,modes,size,'complex'),reps)
    b=cpu(lambda: K._project_half_grid(x,cr,modes,size,'real'),reps)
    c=cpu(lambda: K._project_half_grid(x,None,modes,size,'fft'),reps)
    d=cpu(lambda: fft.dct(x,type=1,axis=-1,workers=1),reps)
    xr=np.ascontiguousarray(x.view(np.float64).reshape(p,h,2).transpose(0,2,1))
    e=cpu(lambda: fft.dct(xr,type=1,axis=-1,workers=1),reps)
    # even extension + rfft on real parts
    def viar():
        full=np.empty((p,2,size)); full[:,:,:h]=xr; full[:,:,h:]=xr[:,:,-2:0:-1]
        return np.fft.rfft(full,axis=-1)[:,:,:m]
    g=cpu(viar,reps)
    ns=1e9/(p*h)
    print(f'size {size:5d} half {h:4d} modes {m} pairs {p}: ns/sample complexGEMM {a*ns:6.2f} realGEMM {b*ns:6.2f} fftpath {c*ns:6.2f} | raw dct complex {d*ns:6.2f} dct real-rows {e*ns:6.2f} evenext+rfft {g*ns:6.2f}')
