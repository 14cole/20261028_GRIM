import sys, time, os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from geos import *
from ghost_backend.twod import solver as S
ang = [0.0, 40.0, 90.0, 150.0, 270.0]; f = 1.5; w = 0.1
strip = [(-w/2, 0.12), (w/2, 0.12)]
body = (3, '3 0 0 1 0', poly_rows(rect(.06, .03)))
g_open = geo([body, (2, '2 0 0 0 0', poly_rows(strip, False))], diel='1 3.0 -0.1 1 0')
g_ref = geo([body, (2, '2 0 0 0 0', poly_rows(rect(w/2, w/1600, 0, 0.12)))], diel='1 3.0 -0.1 1 0')
ref = S.solve_monostatic_rcs_2d(g_ref, [f], ang, geometry_units='meters', solver_method='direct')
for label, fn, kw in (('solve_monostatic_rcs_2d [auto]', S.solve_monostatic_rcs_2d, {}),
                      ('solve_monostatic_rcs_2d [direct]', S.solve_monostatic_rcs_2d, dict(solver_method='direct')),
                      ('solve_monostatic_rcs_2d_survey', S.solve_monostatic_rcs_2d_survey, {}),
                      ('solve_monostatic_rcs_2d_certified [auto]', S.solve_monostatic_rcs_2d_certified, {}),
                      ('solve_monostatic_rcs_2d_certified [direct]', S.solve_monostatic_rcs_2d_certified, dict(solver_method='direct')),
                      ('solve_bistatic_rcs_2d_certified', lambda g, fr, a, **k: S.solve_bistatic_rcs_2d_certified(g, fr, a[:1], a, **k), {})):
    try:
        t = time.time(); r = fn(g_open, [f], ang, geometry_units='meters', **kw); m = r['metadata']
        for pol, lab in (('TE', 'VV'), ('TM', 'HH')):
            b = get(r, pol); br = get(ref, pol)
            if 'bistatic' in label:
                rb = S.solve_bistatic_rcs_2d(g_ref, [f], ang[:1], ang, geometry_units='meters'); br = get(rb, pol)
            d = 20*np.log10(np.abs(b)/np.abs(br))
            print(f'{label:44s} {pol}: dB error vs thin-plate ref {np.round(d, 2)}  max complex rel {np.max(np.abs(b-br))/np.max(np.abs(br)):.2e}')
        mc = m.get('mesh_convergence', {})
        print(f'      gate passed={m["quality_gate"]["passed"]} mesh_certified={m.get("mesh_convergence_certified")} est_published_max_db={mc.get("estimated_published_max_abs_db")} complex_max={mc.get("complex_max_normalized")} warnings={[x[:70] for x in m["warnings"]]} t={time.time()-t:.0f}s', flush=True)
    except Exception as e:
        print(f'{label}: {type(e).__name__}: {str(e)[:300]}', flush=True)
