from lib import *
from ghost_backend.twod import solver as S
from ghost_backend.validation import cylinder as C
a=0.1
for f in (1.0, 3.0):
    g = circle_geo(a, 240)
    t=time.time()
    r = S.solve_monostatic_rcs_2d(g, [f], [0.0, 37.0], geometry_units='meters')
    dt=time.time()-t
    print('keys', list(r.keys())[:40]) if f==1.0 else None
    for s in r['samples'][:4]:
        print(f, dt, {k:(v if not isinstance(v,(list,dict)) else '...') for k,v in s.items()})
    for pol in ('TE','TM'):
        print(pol, C.sigma_pec_cylinder(a, f*1e9, pol), 10*np.log10(C.sigma_pec_cylinder(a, f*1e9, pol)), C.pec_cylinder_backscatter_amplitude(a,f*1e9,pol))
