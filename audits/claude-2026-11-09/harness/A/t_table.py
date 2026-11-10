from ref import *
import ghost_backend.twod.operators as ops
from ghost_backend.twod.assembly.kernels import KernelTable, values, table_reach
import warnings, functools; warnings.simplefilter('ignore')
print=functools.partial(print,flush=True)
h=0.01; e=elem((0,0),(h,0),0)
print("kernel table vs mpmath (max rel err over random r incl. edges):")
mp.mp.dps=30
rng=np.random.RandomState(1)
for k,upper in ((20.0,3.0),(2000.0,1.0),(30-20j,2.0),(5-300j,0.4),(1e-3,10.0),(700-0.01j,3.0)):
    try: T=KernelTable(k,min(upper,table_reach(k)))
    except Exception as ex: print(k,'rejected',ex); continue
    b=T.bounds
    r=np.r_[b[0],b[0]*(1+1e-12),b[1],b[5],b[-1],b[-2],np.exp(rng.uniform(np.log(b[0]),np.log(b[-1]),60)),rng.uniform(b[-1]/2,b[-1],30)]
    got=T.evaluate(r)
    worst=0
    for ri,gi in zip(r,got):
        z=mp.mpc(complex(k).real,complex(k).imag)*mp.mpf(float(ri))
        g=complex(0.25j*mp.hankel2(0,z)); d=complex(0.25j*mp.mpc(complex(k).real,complex(k).imag)*mp.hankel2(1,z))
        worst=max(worst,abs(gi[0]-g)/abs(g)/max(1,abs(k)*ri*8*2.2e-16/2e-13),abs(gi[1]-d)/abs(d)/max(1,abs(k)*ri*8*2.2e-16/2e-13))
    outside=T.evaluate(np.array([b[0]*0.999,b[-1]*1.0000001]))
    print(f"  k={k} intervals={len(b)-1} upper={b[-1]:.3g} backend={T.evidence['evaluation_backend']} worst rel err / tol-model = {worst:.2e} (x2e-13); outside->nan: {np.isnan(outside).all()}")
