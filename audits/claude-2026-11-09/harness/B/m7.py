import sys, time, os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from ref import *
from ghost_backend.twod import solver as S
a = 0.1; n = int(sys.argv[2]) if len(sys.argv) > 2 else 240
which = sys.argv[1].split(',')
k2f = lambda ka: ka*C0/(2*np.pi*a)/1e9
def run(name, g, f, refs, method='direct'):
    t = time.time()
    try:
        r = S.solve_monostatic_rcs_2d(g, [f], [0.0, 77.0], geometry_units='meters', solver_method=method)
    except Exception as e:
        print(f'{name:44s} f={f:<8.5g} [{method}] ERROR {type(e).__name__}: {str(e)[:220]}', flush=True); return
    out = []
    for pol in ('TE', 'TM'):
        b = get(r, pol)[0]; br = refs[pol]
        out.append(f'{pol} rel={abs(b-br)/abs(br):.2e} dB={20*np.log10(abs(b)/abs(br)):+.4f}')
    print(f'{name:44s} f={f:<8.5g} ka={2*np.pi*f*1e9/C0*a:<6.4g} [{method}] np={r["metadata"]["panel_count"]:<5d} {out[0]} | {out[1]} | {r["metadata"]["formulations"]["VV"][:30]} {time.time()-t:.1f}s', flush=True)
def R(f, radii, mats, core): return {p: amp(f*1e9, p, radii, mats, core)[0] for p in ('TE', 'TM')}
for method in ('direct', 'auto'):
    if 'void' in which:
        b = 0.06
        for ka in (0.5, 2.404825557695773, 5.0):
            g = geo([(3, '3 1 0 1 0', rows(a, n)), (3, '3 1 0 1 0', rows(b, n, cw=False))], diel='1 3.0 -0.05 1.2 0')
            run('annulus w/ air void (TYPE3 ccw)', g, k2f(ka), R(k2f(ka), [a, b], [(3-0.05j, 1.2)], ('diel', 1, 1)), method)
    if 'three' in which:
        b, c = 0.08, 0.05
        for ka in (0.5, 2.404825557695773, 5.0):
            g = geo([(3, '3 1 0 1 0', rows(a, n)), (5, '5 1 0 1 2', rows(b, n)), (4, '4 1 0 2 0', rows(c, n))], diel='1 2.0 -0.05 1 0\n2 4.0 -0.1 1.3 0')
            run('air/d1/d2/PEC (3+5+4)', g, k2f(ka), R(k2f(ka), [a, b, c], [(2-0.05j, 1), (4-0.1j, 1.3)], ('pec',)), method)
            g = geo([(3, '3 1 0 1 0', rows(a, n)), (5, '5 1 0 1 2', rows(b, n)), (4, '4 1 9 2 0', rows(c, n))], diel='1 2.0 -0.05 1 0\n2 4.0 -0.1 1.3 0', ibc='9 constant 20 -90 0 0')
            run('air/d1/d2/IBC (3+5+4)', g, k2f(ka), R(k2f(ka), [a, b, c], [(2-0.05j, 1), (4-0.1j, 1.3)], ('ibc', 20-90j)), method)
            g = geo([(3, '3 1 0 1 0', rows(a, n)), (5, '5 1 0 1 2', rows(b, n)), (5, '5 1 0 2 3', rows(c, n))], diel='1 2.0 0 1 0\n2 4.0 0 1.3 0\n3 9 0 1 0')
            run('air/d1/d2/d3 lossless (3+5+5)', g, k2f(ka), R(k2f(ka), [a, b, c], [(2, 1), (4, 1.3)], ('diel', 9, 1)), method)
    if 'split' in which:
        ka = 2.404825557695773; f = k2f(ka)
        th = -np.linspace(0, 2*np.pi, n+1); rr = a*math.sqrt((2*math.pi/n)/math.sin(2*math.pi/n))
        pts = np.c_[rr*np.cos(th), rr*np.sin(th)]
        def seg(i0, i1): return '\n'.join(f'{pts[i,0]:.17g} {pts[i,1]:.17g} {pts[i+1,0]:.17g} {pts[i+1,1]:.17g}' for i in range(i0, i1))
        cuts = [0, n//5, n//2, n-7, n]
        g = geo([(2, '2 1 0 0 0', seg(cuts[i], cuts[i+1])) for i in range(4)])
        run('PEC circle split in 4 segments', g, f, R(f, [a], [], ('pec',)), method)
        g = geo([(2, '2 1 7 0 0', seg(cuts[i], cuts[i+1])) for i in range(4)], ibc='7 constant 100 50 0 0')
        run('IBC circle split in 4 segments', g, f, R(f, [a], [], ('ibc', 100+50j)), method)
        g = geo([(2, f'2 1 {7+i} 0 0', seg(cuts[i], cuts[i+1])) for i in range(4)], ibc='\n'.join(f'{7+i} constant 100 50 0 0' for i in range(4)))
        run('IBC circle 4 segs, 4 equal-valued flags', g, f, R(f, [a], [], ('ibc', 100+50j)), method)
        g = geo([(3, '3 1 0 1 0', seg(cuts[i], cuts[i+1])) for i in range(4)], diel='1 3.0 -0.05 1.2 0')
        run('DIEL circle split in 4 segments', g, f, R(f, [a], [], ('diel', 3-0.05j, 1.2)), method)
        g = geo([(3, '3 1 0 1 0', seg(cuts[i], cuts[i+1])) for i in range(4)] + [(4, '4 1 0 1 0', rows(0.06, n))], diel='1 3.0 -0.05 1.2 0')
        run('COAT outer split in 4 segments', g, f, R(f, [a, .06], [(3-0.05j, 1.2)], ('pec',)), method)
        g = geo([(3, '3 1 0 1 0', seg(0, n//2)), (3, '3 1 0 2 0', seg(n//2, n))], diel='1 3.0 -0.05 1.2 0\n2 3.0 -0.05 1.2 0')
        run('DIEL circle, 2 flags w/ equal values', g, f, R(f, [a], [], ('diel', 3-0.05j, 1.2)), method)
        g = geo([(2, '2 1 0 0 0', rows(a, n))], ibc='7 constant 100 50 0 0', diel='5 9 -1 2 0')
        run('PEC + unused material rows', g, f, R(f, [a], [], ('pec',)), method)
        g = geo([(2, '2 1 7 0 0', rows(a, n))], ibc='7 constant 0 0 0 0')
        run('IBC flag with Zs=0 (PEC limit)', g, f, R(f, [a], [], ('pec',)), method)
    if 'shell' in which:
        for zs in ('200 0', '50 -120', '5 0', '3000 500'):
            z = complex(*map(float, zs.split()))
            for ka in (0.5, 2.404825557695773, 5.0):
                f = k2f(ka)
                g = geo([(1, '1 1 7 0 0', rows(a, n))], ibc=f'7 constant {zs} 0 0')
                run(f'closed TYPE1 sheet shell Zs={zs}', g, f, {p: shell_amp(f*1e9, p, a, z)[0] for p in ('TE', 'TM')}, method)
                g = geo([(1, '1 1 7 0 0', rows(a, n, cw=False))], ibc=f'7 constant {zs} 0 0')
                run(f'  same, ccw', g, f, {p: shell_amp(f*1e9, p, a, z)[0] for p in ('TE', 'TM')}, method)
    if 'thin' in which:
        for d, em in ((0.0005, '3 -0.02 1 0'), (0.002, '3 -0.02 1 0'), (0.0005, '2.5 -0.04 1.3 -0.02')):
            e = list(map(float, em.split())); eps = complex(e[0], e[1]); mu = complex(e[2], e[3])
            for ka in (0.5, 2.404825557695773):
                f = k2f(ka)
                g = geo([(1, '1 1 7 0 0', rows(a, n))], ibc=f'7 thin_dielectric {d} 2', diel=f'2 {em}')
                run(f'thin layer shell d={d} eps,mu={em}', g, f, R(f, [a+d/2, a-d/2], [(eps, mu)], ('diel', 1, 1)), method)
