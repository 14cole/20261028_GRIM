from ref import *
from ghost_backend.twod.assembly import kernels as K
from ghost_backend.twod.basis import plane_wave_moments
import warnings; warnings.simplefilter('ignore')
rng=np.random.RandomState(0)
worst=0; worstp=0
t,w=gl(200)
for trial in range(400):
    L=10**rng.uniform(-4,0); kL=10**rng.uniform(-6,2.3); k=kL/L
    a=rng.uniform(0,2*np.pi); p0=rng.uniform(-1,1,2); p1=p0+L*np.array([np.cos(a),np.sin(a)])
    e=elem(p0,p1); ang=rng.uniform(0,360,5)
    got=K.incident.__wrapped__(e,k,ang)
    d=K.directions(ang); pts=p0+t[:,None]*(p1-p0)
    ph=np.exp(1j*k*(pts@d.T))
    ref=L*np.stack(((w*(1-t))@ph,(w*t)@ph))
    if kL<300: worst=max(worst,np.max(abs(got-ref))/L)
    for deg in (2,3):
        if kL>200: continue
        gotp=plane_wave_moments(np.array([e.center]),np.array([p1-p0]),np.array([L]),k,d,deg)[0]
        from ghost_backend.twod.basis import values
        refp=L*(values(t,deg)*w[:,None]).T@ph
        worstp=max(worstp,np.max(abs(gotp-refp))/L)
print('linear plane-wave moments worst abs err / L (kL 1e-6..200):',worst,' polynomial deg2/3:',worstp)
