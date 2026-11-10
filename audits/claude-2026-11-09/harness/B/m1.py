import sys, time
from ref import *
from ghost_backend.twod import solver as S
from ghost_backend.validation import cylinder as C
a = 0.1
def run(name, g, f, radii, mats, core, units='meters'):
    t = time.time()
    try:
        r = S.solve_monostatic_rcs_2d(g, [f], [0.0], geometry_units=units)
    except Exception as e:
        print(f'{name:38s} f={f:<8g} ERROR {type(e).__name__}: {str(e)[:150]}'); return
    dt = time.time()-t
    out = []
    for pol in ('TE', 'TM'):
        b = get(r, pol)[0]; br = amp(f*1e9, pol, radii, mats, core)[0]
        out.append(f'{pol} rel={abs(b-br)/abs(br):.2e} dB={20*np.log10(abs(b)/abs(br)):+.4f}')
    print(f'{name:38s} f={f:<8g} ka={2*np.pi*f*1e9/C0*radii[0]:<7.4g} np={r["metadata"]["panel_count"]:<5d} {out[0]} | {out[1]} | {dt:.1f}s', flush=True)

which = sys.argv[1] if len(sys.argv) > 1 else 'all'
n = int(sys.argv[2]) if len(sys.argv) > 2 else 360
k2f = lambda ka: ka*C0/(2*np.pi*a)/1e9
if which in ('pec', 'all'):
    g = geo([(2, '2 1 0 0 0', rows(a, n))])
    for ka in (0.001, 0.05, 0.5, 2.404825557695773, 3.8317059702075125, 1.8411837813406593, 5.0, 5.520078110286311, 10.0):
        run('PEC', g, k2f(ka), [a], [], ('pec',))
if which in ('ibc', 'all'):
    for zs in ('1e-4 0', '37 0', '377 0', '0 100', '0 -100', '50 -200', '1e5 0', '1e-3 300', '0.001 -377'):
        g = geo([(2, '2 1 7 0 0', rows(a, n))], ibc=f'7 constant {zs} 0 0')
        z = complex(*map(float, zs.split()))
        for ka in (0.05, 2.404825557695773, 5.0):
            run(f'IBC Zs={zs}', g, k2f(ka), [a], [], ('ibc', z))
if which in ('diel', 'all'):
    for em in ('4 0 1 0', '4 -0.2 1 0', '2.5 -0.04 1.3 -0.02', '1 0 3 0', '12 -1 1 0', '1.0001 0 1 0'):
        e = list(map(float, em.split())); eps = complex(e[0], e[1]); mu = complex(e[2], e[3])
        g = geo([(3, '3 1 0 1 0', rows(a, n))], diel=f'1 {em}')
        for ka in (0.01, 1.0, 2.404825557695773, 3.8317059702075125, 5.0):
            run(f'DIEL eps,mu={em}', g, k2f(ka), [a], [], ('diel', eps, mu))
if which in ('coat', 'all'):
    b = 0.07
    for em in ('3 0 1 0', '2.8 -0.06 1.2 -0.1'):
        e = list(map(float, em.split())); eps = complex(e[0], e[1]); mu = complex(e[2], e[3])
        for ka in (0.05, 1.0, 2.404825557695773, 5.0):
            g = geo([(3, '3 1 0 1 0', rows(a, n)), (4, '4 1 0 1 0', rows(b, n))], diel=f'1 {em}')
            run(f'COATPEC {em}', g, k2f(ka), [a, b], [(eps, mu)], ('pec',))
            g = geo([(3, '3 1 0 1 0', rows(a, n)), (4, '4 1 9 1 0', rows(b, n))], diel=f'1 {em}', ibc='9 constant 35 80 0 0')
            run(f'COATIBC 35+80j {em}', g, k2f(ka), [a, b], [(eps, mu)], ('ibc', 35+80j))
            g = geo([(3, '3 1 0 1 0', rows(a, n)), (5, '5 1 0 1 2', rows(b, n))], diel=f'1 {em}\n2 4.4 -0.1 1.5 0')
            run(f'2LAYER {em}/4.4-.1j,1.5', g, k2f(ka), [a, b], [(eps, mu)], ('diel', 4.4-0.1j, 1.5))
