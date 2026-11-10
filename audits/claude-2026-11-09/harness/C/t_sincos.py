from common import *
rng=np.random.default_rng(0); p=4000
rp,zp,rq,zq=rng.uniform(0.01,1,(4,p))
_,_,sin2,cx,sx=K._half_grid_tables(256,np.arange(4),True,'complex')
sg=K._native_pair_sampler('g')
R=np.sqrt(((rp-rq)**2+(zp-zq)**2)[:,None]+4*(rp*rq)[:,None]*sin2)
for k in (1e2,1e4,1e6,1e8,1e10,1e12):
    g=sg((rp,zp,rq,zq),complex(k),sin2,1)
    ref=np.exp(-1j*np.float64(k)*R)/(4*np.pi*R)
    print(f'k={k:g} max kR={k*R.max():.1e}  max rel err native vs numpy {np.max(np.abs(g-ref)/np.abs(ref)):.2e}  finite {np.isfinite(g).all()}')
