import sys, time, os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from geos import *
from ghost_backend.twod import solver as S
def single(g, f, ang, pol, method='direct', **kw):
    r = S.solve_monostatic_rcs_2d_single_polarization(g, [f], ang, pol, geometry_units='meters', solver_method=method, **kw)
    return np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in r['samples']]), r
def rel(a, b): return float(np.max(np.abs(a-b))/np.max(np.abs(b)))
ang = [0.0, 40.0, 90.0, 150.0, 270.0]
which = sys.argv[1].split(',')
if 'openTE' in which:
    # dielectric body + separate open PEC strip, TE
    w = 0.1; t = w/200; f = 1.5
    strip = [(-w/2, 0.12), (w/2, 0.12)]
    body = (3, '3 0 0 1 0', poly_rows(rect(.06, .03)))
    for pol in ('TE', 'TM'):
        out = {}
        for label, extra in (('open TYPE2 strip', (2, '2 0 0 0 0', poly_rows(strip, False))),
                             ('thin closed plate t=w/200', (2, '2 0 0 0 0', poly_rows(rect(w/2, t/2, 0, 0.12)))),
                             ('thin closed plate t=w/800', (2, '2 0 0 0 0', poly_rows(rect(w/2, t/8, 0, 0.12))))):
            try:
                g = geo([body, extra], diel='1 3.0 -0.1 1 0')
                b, r = single(g, f, ang, pol)
                out[label] = b
                print(f'{pol} diel+{label:26s} np={r["metadata"]["panel_count"]} form={r["metadata"]["formulation"][:50]} warnings={len(r["metadata"]["warnings"])} |B|=', np.round(np.abs(b), 4), flush=True)
                for wmsg in r['metadata']['warnings']: print('     W:', wmsg[:160])
            except Exception as e:
                print(f'{pol} diel+{label}: {type(e).__name__}: {str(e)[:200]}', flush=True)
        if 'open TYPE2 strip' in out and 'thin closed plate t=w/800' in out:
            print(f'   {pol}: open strip vs t=w/800 plate rel diff {rel(out["open TYPE2 strip"], out["thin closed plate t=w/800"]):.3e};  plate t=w/200 vs t=w/800 {rel(out["thin closed plate t=w/200"], out["thin closed plate t=w/800"]):.3e}')
if 'res' in which:
    a = 0.1
    for ka in (2.404825557695773, 2.30, 5.520078110286311):
        f = ka*C0/(2*np.pi*a)/1e9
        strip = [(0.14, -0.04), (0.14, 0.04)]
        g_open = geo([(2, '2 1 0 0 0', rows(a, 240)), (2, '2 -40 0 0 0', poly_rows(strip, False))])
        g_sheet = geo([(2, '2 1 0 0 0', rows(a, 240)), (1, '1 -40 7 0 0', poly_rows(strip, False))], ibc='7 constant 1e-7 0 0 0')
        b1, r1 = single(g_open, f, ang, 'TM', compute_condition_number=True, strict_quality_gate=False)
        b2, r2 = single(g_sheet, f, ang, 'TM', compute_condition_number=True, strict_quality_gate=False)
        b3, r3 = single(g_open, f, ang, 'TM')
        print(f'TM closed PEC circle + open strip ka={ka:.4f}: TYPE2-open [{r1["metadata"]["formulation"][:34]}] cond={r1["metadata"]["condition_est_max"]:.3g} gate={r1["metadata"]["quality_gate"]["passed"]} | TYPE1(Zs~0) [{r2["metadata"]["formulation"][:60]}] cond={r2["metadata"]["condition_est_max"]:.3g} | rel diff {rel(b1, b2):.2e} | default-gate passed={r3["metadata"]["quality_gate"]["passed"]} warnings={r3["metadata"]["warnings"]}', flush=True)
