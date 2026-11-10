import sys, time, os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from geos import *
from ghost_backend.twod import solver as S
which = sys.argv[1].split(',')
def single(g, f, ang, pol, method='direct', **kw):
    r = S.solve_monostatic_rcs_2d_single_polarization(g, [f], ang, pol, geometry_units='meters', solver_method=method, **kw)
    return np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in r['samples']]), r
def rel(a, b): return float(np.max(np.abs(a-b))/np.max(np.abs(b)))
if 'conv' in which:
    a = 0.1; f = 2.404825557695773*C0/(2*np.pi*a)/1e9
    cases = {'PEC': (lambda n: geo([(2, '2 1 0 0 0', rows(a, n))]), [a], [], ('pec',)),
             'IBC 100+50j': (lambda n: geo([(2, '2 1 7 0 0', rows(a, n))], ibc='7 constant 100 50 0 0'), [a], [], ('ibc', 100+50j)),
             'DIEL 3-.05j,1.2': (lambda n: geo([(3, '3 1 0 1 0', rows(a, n))], diel='1 3 -0.05 1.2 0'), [a], [], ('diel', 3-0.05j, 1.2)),
             'COAT PEC': (lambda n: geo([(3, '3 1 0 1 0', rows(a, n)), (4, '4 1 0 1 0', rows(.06, n))], diel='1 3 -0.05 1.2 0'), [a, .06], [(3-0.05j, 1.2)], ('pec',)),
             'SHELL 200ohm': (lambda n: geo([(1, '1 1 7 0 0', rows(a, n))], ibc='7 constant 200 0 0 0'), None, None, None)}
    for name, (mk, radii, mats, core) in cases.items():
        for pol in ('TE', 'TM'):
            br = amp(f*1e9, pol, radii, mats, core)[0] if radii else shell_amp(f*1e9, pol, a, 200.0)[0]
            errs = []
            for n in (30, 60, 120, 240, 480):
                b, _ = single(mk(n), f, [0.0], pol)
                errs.append(abs(b[0]-br)/abs(br))
            print(f'conv {name:16s} {pol} n=30..480 err:', ' '.join(f'{e:.2e}' for e in errs), ' orders:', ' '.join(f'{np.log2(errs[i]/errs[i+1]):.2f}' for i in range(4)), flush=True)
if 'rectconv' in which:
    f = 1.5
    for name in ('pec', 'pecibc', 'diel', 'coatibc', 'two', 'sheet', 'sheetpec', 'thin'):
        for pol in ('TE', 'TM'):
            vals = []
            try:
                for N in (-10, -20, -40, -80, -160):
                    b, r = single(make(name, N=N), f, [0.0, 35.0, 110.0], pol); vals.append(b)
                d = [rel(vals[i], vals[-1]) for i in range(4)]
                print(f'rectconv {name:9s} {pol} N=-10..-80 vs -160:', ' '.join(f'{e:.2e}' for e in d), ' np(-160)=', r['metadata']['panel_count'], flush=True)
            except Exception as e:
                print(f'rectconv {name} {pol} ERROR', str(e)[:200])
if 'strip' in which:
    w = 0.3
    for f in (1.0, 3.0, 10.0):
        k = 2*np.pi*f*1e9/C0
        gs = geo([(2, '2 0 0 0 0', poly_rows([(-w/2, 0), (w/2, 0)], False))])
        gf = geo([(2, '2 -80 0 0 0', poly_rows([(-w/2, 0), (w/2, 0)], False))])
        ang = [90.0, 60.0, 30.0, 5.0]
        b, r = single(gs, f, ang, 'TM'); bf, rf = single(gf, f, ang, 'TM')
        gsh = geo([(1, '1 0 7 0 0', poly_rows([(-w/2, 0), (w/2, 0)], False))], ibc='7 constant 1e-6 0 0 0')
        bs, _ = single(gsh, f, ang, 'TM')
        # thin closed PEC plate (t = w/300) TM
        t = w/300
        gp = geo([(2, '2 0 0 0 0', poly_rows(rect(w/2, t/2)))])
        bp, _ = single(gp, f, ang, 'TM')
        po = k*w*w   # broadside PO sigma_2D
        print(f'strip TM kw={k*w:.1f} np={r["metadata"]["panel_count"]}/{rf["metadata"]["panel_count"]} auto-vs-fine {rel(b, bf):.2e} | TYPE1 Zs=1e-6 vs TYPE2 strip {rel(bs, b):.2e} | thin closed plate vs strip {rel(bp, b):.2e} | broadside sigma/PO = {abs(b[0])**2/(4*k)/po:.4f} form={r["metadata"]["formulation"][:40]}', flush=True)
        # TE: sheet with tiny Zs vs thin closed plate
        try:
            bte_s, r1 = single(gsh, f, ang, 'TE'); bte_p, r2 = single(gp, f, ang, 'TE')
            gshf = geo([(1, '1 -80 7 0 0', poly_rows([(-w/2, 0), (w/2, 0)], False))], ibc='7 constant 1e-6 0 0 0')
            bte_f, _ = single(gshf, f, ang, 'TE')
            print(f'      TE kw={k*w:.1f} TYPE1 Zs=1e-6 sheet vs thin closed PEC plate {rel(bte_s, bte_p):.2e} per-angle {np.abs(bte_s-bte_p)/np.abs(bte_p)} | sheet auto-vs-fine {rel(bte_s, bte_f):.2e} | |B| {np.abs(bte_s)}', flush=True)
        except Exception as e: print('      TE ERROR', str(e)[:200])
        try:
            S.solve_monostatic_rcs_2d(gs, [f], ang, geometry_units='meters')
        except Exception as e: print('      co-pol open TYPE2:', type(e).__name__, str(e)[:120])
if 'optical' in which:
    f = 1.5; k = 2*np.pi*f*1e9/C0
    obs = list(np.arange(0.0, 360.0, 1.0))
    for name in ('pec', 'diel_ll', 'sheetpec'):
        g = make(name, N=-40)
        inc = [20.0]
        r = S.solve_bistatic_rcs_2d(g, [f], inc, obs, geometry_units='meters')
        for lab in ('VV', 'HH'):
            B = np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in r['co_solved_samples'][lab]])
            sig_s = np.mean(np.abs(B)**2/(4*k))          # (1/2pi) int sigma dphi
            fwd = B[200]/(-4j)
            sig_ext = -(4/k)*fwd.real
            print(f'optical {name:8s} {lab} sigma_scat={sig_s:.6f} sigma_ext={sig_ext:.6f} ratio={sig_s/sig_ext:.6f}', flush=True)
    # analytic sanity of the formula
    B = amp(f*1e9, 'TM', [0.1], [], ('pec',), np.arange(0, 360.0)); Bf = amp(f*1e9, 'TM', [0.1], [], ('pec',), 180.0)[0]
    print('optical formula check (analytic PEC):', np.mean(np.abs(B)**2/(4*k)) / (-(4/k)*(Bf/(-4j)).real))
