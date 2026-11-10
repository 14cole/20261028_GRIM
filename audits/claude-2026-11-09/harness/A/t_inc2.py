from ref import *
from ghost_backend.twod.assembly import kernels as K
import warnings; warnings.simplefilter('ignore')
mp.mp.dps=40
# exact linear moments: I1 = int_0^1 t e^{i z t} dt, I0 = int_0^1 (1-t) e^{izt} dt, compare code formula via moments() with center phase removed
for z in (1e-9,1e-4,0.019,0.0201,0.021,0.05,0.5,3.0,50.0,500.0,5000.0):
    L=1.0; e=elem((0,0),(L,0)); k=z/L
    got=K.incident.__wrapped__(e,k,[0.0])[:,0]
    zz=mp.mpf(z)
    I1=complex(mp.quad(lambda t:t*mp.exp(1j*zz*t),mp.linspace(0,1,max(2,int(z/3)+2))))
    I0=complex(mp.quad(lambda t:(1-t)*mp.exp(1j*zz*t),mp.linspace(0,1,max(2,int(z/3)+2))))
    print(f"z=kL={z}: abs err I0 {abs(got[0]-I0):.1e} I1 {abs(got[1]-I1):.1e}  (|I0|={abs(I0):.2e})")
