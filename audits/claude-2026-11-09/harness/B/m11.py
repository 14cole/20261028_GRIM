import sys, time, os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from geos import *
from ghost_backend.twod import solver as S
a = 0.1; f = 5.0*C0/(2*np.pi*a)/1e9
cases = {'PEC circle 64-gon N=0': (geo([(2, '2 0 0 0 0', rows(a, 64))]), [a], [], ('pec',)),
         'IBC circle 64-gon N=0': (geo([(2, '2 0 7 0 0', rows(a, 64))], ibc='7 constant 100 50 0 0'), [a], [], ('ibc', 100+50j)),
         'COAT circle 64-gon N=0': (geo([(3, '3 0 0 1 0', rows(a, 64)), (4, '4 0 0 1 0', rows(.06, 64))], diel='1 3 -0.05 1.2 0'), [a, .06], [(3-0.05j, 1.2)], ('pec',))}
for name, (g, radii, mats, core) in cases.items():
    for method in ('direct', 'auto'):
        t = time.time(); rp = S.solve_monostatic_rcs_2d(g, [f], [0.0, 30.0], geometry_units='meters', solver_method=method); tp = time.time()-t
        t = time.time(); rc = S.solve_monostatic_rcs_2d_certified(g, [f], [0.0, 30.0], geometry_units='meters', solver_method=method); tc = time.time()-t
        mc = rc['metadata']['mesh_convergence']
        line = f'{name:24s} [{method}] plain {tp:.1f}s np={rp["metadata"]["panel_count"]} | certified {tc:.1f}s base/fine panels {mc.get("base_panel_count")}/{mc.get("fine_panel_count")} strategy={rc["metadata"].get("mesh_strategy_used")} adaptive={ (rc["metadata"].get("adaptive_mesh") or {}).get("used")}'
        for pol in ('TE', 'TM'):
            br = amp(f*1e9, pol, radii, mats, core)[0]
            ch = mc['channels']['VV' if pol == 'TE' else 'HH']
            line += f' | {pol} true err plain {abs(get(rp, pol)[0]-br)/abs(br):.1e} cert {abs(get(rc, pol)[0]-br)/abs(br):.1e} est_pub {ch.get("estimated_published_complex_max_normalized"):.1e} base-fine {ch.get("complex_max_normalized"):.1e}'
        print(line, flush=True)
