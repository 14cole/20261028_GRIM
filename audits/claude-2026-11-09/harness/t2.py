from lib import *
from ghost_backend.bor import dispatch as D
from ghost_backend.validation import sphere as SP
a=0.1
for f in (1.0, 3.0):
    g = bor_sphere(a, 60)
    t=time.time()
    r = D.solve_monostatic_rcs_bor(g, [f], [0.0, 60.0, 90.0], geometry_units='meters')
    dt=time.time()-t
    if f==1.0: print(list(r.keys())); print({k:(v if not isinstance(v,(list,dict)) else type(v).__name__) for k,v in r['metadata'].items()})
    for s in r['samples']:
        print(f, round(dt,2), s.get('polarization'), s.get('theta_inc_deg'), s.get('rcs_linear'), s.get('rcs_db'))
    print('exact', SP.sigma_pec_sphere(a, f*1e9), 10*np.log10(SP.sigma_pec_sphere(a, f*1e9)))
