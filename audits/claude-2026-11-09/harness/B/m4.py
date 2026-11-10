import sys, time, os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from geos import *
from ghost_backend.twod import solver as S
F = 1.5; ANG = [0.0, 35.0, 110.0, 200.0, 290.0]
method = sys.argv[1]
names = sys.argv[2].split(',')
tests = sys.argv[3].split(',') if len(sys.argv) > 3 else ['rot', 'tr', 'units', 'order', 'bi', 'recip']
def rel(a, b): return float(np.max(np.abs(a-b))/np.max(np.abs(b)))
def mono(g, f, ang, units='meters', **kw):
    r = S.solve_monostatic_rcs_2d(g, f, ang, geometry_units=units, solver_method=method, **kw)
    return {p: get(r, p) for p in ('TE', 'TM')}, r
k = 2*np.pi*F*1e9/C0
for name in names:
    try:
        g = make(name); t = time.time()
        b0, r0 = mono(g, [F], ANG)
        line = f"{name:9s}[{method}] np={r0['metadata']['panel_count']}"
        if 'rot' in tests:
            al = 23.0
            b1, _ = mono(make(name, rot=math.radians(al)), [F], [a+al for a in ANG])
            line += ' | rot TE %.1e TM %.1e' % (rel(b1['TE'], b0['TE']), rel(b1['TM'], b0['TM']))
        if 'tr' in tests:
            d = np.array([0.37, -0.21])
            b1, _ = mono(make(name, shift=tuple(d)), [F], ANG)
            ph = np.array([np.exp(2j*k*(d[0]*math.cos(math.radians(a))+d[1]*math.sin(math.radians(a)))) for a in ANG])
            line += ' | transl(+2jkd.r) TE %.1e TM %.1e' % (rel(b1['TE'], b0['TE']*ph), rel(b1['TM'], b0['TM']*ph))
        if 'units' in tests:
            b1, _ = mono(make(name, scale=1/0.0254), [F], ANG, units='inches')
            line += ' | inches TE %.1e TM %.1e' % (rel(b1['TE'], b0['TE']), rel(b1['TM'], b0['TM']))
        if 'order' in tests:
            F2 = 1.1
            ra = S.solve_monostatic_rcs_2d(g, [F, F2], ANG, geometry_units='meters', solver_method=method)
            rb = S.solve_monostatic_rcs_2d(g, [F2, F], ANG, geometry_units='meters', solver_method=method)
            e = []
            for p in ('TE', 'TM'):
                e.append(max(rel(get(ra, p, F), b0[p]), rel(get(rb, p, F), b0[p]), rel(get(ra, p, F2), get(rb, p, F2))))
            fo = [s['frequency_ghz'] for s in rb['samples']][::2*len(ANG)]
            line += ' | multi-f/order TE %.1e TM %.1e order=%s' % (e[0], e[1], fo)
        if 'bi' in tests or 'recip' in tests:
            rbi = S.solve_bistatic_rcs_2d(g, [F], ANG, ANG, geometry_units='meters')
            for p, lab in (('TE', 'VV'), ('TM', 'HH')):
                M = np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in rbi['co_solved_samples'][lab]]).reshape(len(ANG), len(ANG))
                line += ' | %s bi-diag-vs-mono %.1e recip %.1e' % (p, rel(np.diag(M), b0[p]), float(np.max(np.abs(M-M.T))/np.max(np.abs(M))))
            line += ' bi_np=%d' % rbi['metadata']['panel_count']
        print(line + ' | %.0fs' % (time.time()-t), flush=True)
    except Exception as e:
        import traceback
        print(f'{name:9s}[{method}] ERROR {type(e).__name__}: {str(e)[:300]}', flush=True)
