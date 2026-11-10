import sys, time, os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from geos import *
from ghost_backend.twod import solver as S
ang = [0.0, 40.0, 90.0, 150.0, 270.0]; f = 1.5; w = 0.1
sheet = (1, '1 0 7 0 0', poly_rows([(-.08, .09), (.09, 0.08)], False))
strip = [(-w/2, 0.0), (w/2, 0.0)]
def single(g, pol, **kw):
    r = S.solve_monostatic_rcs_2d_single_polarization(g, [f], ang, pol, geometry_units='meters', solver_method='direct', **kw)
    return np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in r['samples']]), r
for N in (0, -80):
    g_t2 = geo([sheet, (2, f'2 {N} 0 0 0', poly_rows(strip, False))], ibc='7 constant 150 60 0 0')
    g_t1 = geo([sheet, (1, f'1 {N} 8 0 0', poly_rows(strip, False))], ibc='7 constant 150 60 0 0\n8 constant 1e-7 0 0 0')
    g_pl = geo([sheet, (2, f'2 {N} 0 0 0', poly_rows(rect(w/2, w/1600)))], ibc='7 constant 150 60 0 0')
    for pol in ('TE', 'TM'):
        res = {}
        for lab, g in (('sheet+open TYPE2 strip', g_t2), ('sheet+TYPE1 Zs~0 strip', g_t1), ('sheet+thin closed plate', g_pl)):
            try:
                b, r = single(g, pol); res[lab] = b
                print(f'N={N} {pol} {lab:26s} np={r["metadata"]["panel_count"]} |B|={np.round(np.abs(b), 4)} form={r["metadata"]["formulation"][:36]} warn={[x[:60] for x in r["metadata"]["warnings"]]}', flush=True)
            except Exception as e:
                print(f'N={N} {pol} {lab}: {type(e).__name__}: {str(e)[:160]}', flush=True)
        if len(res) == 3:
            ref = res['sheet+thin closed plate']
            print(f'   {pol}: dB err vs plate: TYPE2-open {np.round(20*np.log10(np.abs(res["sheet+open TYPE2 strip"])/np.abs(ref)), 2)}  TYPE1~0 {np.round(20*np.log10(np.abs(res["sheet+TYPE1 Zs~0 strip"])/np.abs(ref)), 2)}')
