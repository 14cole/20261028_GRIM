import sys, time, traceback
from geos import *
from ghost_backend.twod import solver as S
F = 1.5; ANG = [0.0, 35.0, 110.0, 200.0, 290.0]
names = sys.argv[2].split(',') if len(sys.argv) > 2 else ALL
method = sys.argv[1]
def rel(a, b): return float(np.max(np.abs(a-b))/np.max(np.abs(b)))
for name in names:
    try:
        g = make(name)
        t = time.time(); r = S.solve_monostatic_rcs_2d(g, [F], ANG, geometry_units='meters', solver_method=method); dt = time.time()-t
        m = r['metadata']
        line = f"{name:9s} [{method}] np={m['panel_count']} form={m['formulations']['VV'][:28]!r} t={dt:.1f}s reuse={m.get('assembled_system_reuses')}"
        for pol in ('TE', 'TM'):
            b = get(r, pol)
            s1 = S.solve_monostatic_rcs_2d_single_polarization(g, [F], ANG, pol, geometry_units='meters', solver_method=method)
            b1 = np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in s1['samples']])
            line += f" | {pol} co-vs-single={rel(b, b1):.1e}"
        print(line, flush=True)
    except Exception as e:
        print(f'{name:9s} [{method}] ERROR {type(e).__name__}: {str(e)[:200]}', flush=True)
