"""Independent layered-cylinder reference (exp(+jwt), H^(2)), complex B amplitude."""
import sys, math
sys.path.insert(0, '/tmp/claude-0/-home-user-20261028-GRIM/37e475f6-6ce5-5f61-b336-1c9c4571e452/scratchpad/audit')
import numpy as np
import lib
from scipy import special as sp
C0 = 299792458.0; ETA0 = 376.730313668

def coeffs(freq_hz, pol, radii, mats, core, nmax=None):
    """radii: descending list [a1 (outer), a2, ...]; mats: list of (eps,mu) for layers between radii
    (len = len(radii)-1) ; core: ('pec',) | ('ibc', Zs) | ('diel', eps, mu) inside the last radius."""
    k0 = 2*math.pi*freq_hz/C0
    kmax = k0*radii[0]*max([1.0]+[abs(np.sqrt(complex(e)*complex(m))) for e,m in mats]+([abs(np.sqrt(complex(core[1])*complex(core[2])))] if core[0]=='diel' else []))
    if nmax is None: nmax = int(kmax + 4.05*kmax**(1/3) + 12)
    out = {}
    for n in range(0, nmax+1):
        # unknowns: a (ext), then (b,c) per layer, then d for diel core
        L = len(mats)
        nun = 1 + 2*L + (1 if core[0]=='diel' else 0)
        A = np.zeros((nun, nun), complex); rhs = np.zeros(nun, complex)
        row = 0
        def med(i):  # i=0 air, 1..L layers
            if i == 0: return 1.0+0j, 1.0+0j
            return complex(mats[i-1][0]), complex(mats[i-1][1])
        def basis(i, r):
            """returns list of (col, value, dvalue/dr /p) and inhomogeneous (val, dval/p)"""
            e, m = med(i); k = k0*np.sqrt(e*m); p = m if pol=='TM' else e
            if i == 0:
                return [(0, sp.hankel2(n, k*r), k*sp.h2vp(n, k*r)/p)], (sp.jv(n, k*r), k*sp.jvp(n, k*r)/p)
            c0 = 1+2*(i-1)
            return [(c0, sp.hankel1(n, k*r), k*sp.h1vp(n, k*r)/p), (c0+1, sp.hankel2(n, k*r), k*sp.h2vp(n, k*r)/p)], (0, 0)
        for j, r in enumerate(radii):
            outer, inh = basis(j, r)
            last = (j == len(radii)-1)
            if not last:
                inner, _ = basis(j+1, r)
                for c, v, dv in outer: A[row, c] += v; A[row+1, c] += dv
                for c, v, dv in inner: A[row, c] -= v; A[row+1, c] -= dv
                rhs[row] = -inh[0]; rhs[row+1] = -inh[1]; row += 2
            else:
                e, m = med(j); p = m if pol=='TM' else e
                if core[0] == 'diel':
                    ec, mc = complex(core[1]), complex(core[2]); kc = k0*np.sqrt(ec*mc); pc = mc if pol=='TM' else ec
                    c = nun-1
                    for cc, v, dv in outer: A[row, cc] += v; A[row+1, cc] += dv
                    A[row, c] -= sp.jv(n, kc*r); A[row+1, c] -= kc*sp.jvp(n, kc*r)/pc
                    rhs[row] = -inh[0]; rhs[row+1] = -inh[1]; row += 2
                else:
                    if core[0] == 'pec':
                        wu, wd = (1, 0) if pol == 'TM' else (0, 1)
                    else:
                        Zs = complex(core[1])
                        beta = -1j*k0*m*ETA0/Zs if pol == 'TM' else -1j*k0*e*Zs/ETA0
                        wu, wd = beta, 1
                    # du/dr = p * (dv/p)
                    for cc, v, dv in outer: A[row, cc] += wu*v + wd*p*dv
                    rhs[row] = -(wu*inh[0] + wd*p*inh[1]); row += 1
        # scale columns for conditioning
        s = np.max(np.abs(A), axis=0); s[s==0] = 1
        if not (np.all(np.isfinite(A)) and np.all(np.isfinite(rhs))): break
        try: x = np.linalg.solve(A/s, rhs)/s
        except np.linalg.LinAlgError: break
        if not np.isfinite(x[0]): break
        out[n] = x[0]
    return out

def amp(freq_hz, pol, radii, mats, core, dphi_deg=0.0):
    """B amplitude; dphi = phi_scat - phi_inc (deg). dphi=0 -> backscatter"""
    a = coeffs(freq_hz, pol, radii, mats, core)
    d = np.radians(np.atleast_1d(dphi_deg))
    f = np.zeros(d.shape, complex)
    for n, an in a.items():
        f += an*(-1)**n*(1 if n == 0 else 2*np.cos(n*d))
    return -4j*f

def rows(a, n, cw=True, x0=0.0, y0=0.0, rot=0.0, scale=1.0):
    th = np.linspace(0, 2*np.pi, n+1) + rot
    if cw: th = -th
    r = a*math.sqrt((2*math.pi/n)/math.sin(2*math.pi/n))*scale
    x = x0*scale + r*np.cos(th); y = y0*scale + r*np.sin(th)
    return '\n'.join(f'{x[i]:.17g} {y[i]:.17g} {x[i+1]:.17g} {y[i+1]:.17g}' for i in range(n))

def geo(segs, ibc='', diel=''):
    """segs: list of (typ, props, rows)"""
    from lib import snap
    t = "Title: c\n"
    for i, (typ, props, r) in enumerate(segs):
        t += f"Segment: s{i} {typ}\nproperties: {props}\n{r}\n\n"
    t += f"IBCS_Resistances:\n{ibc}\nDielectrics:\n{diel}\n"
    return snap(t)

def get(res, pol, f=None):
    """complex amps for pol in ('TE','TM') from co-pol result, request order"""
    lab = {'TE': 'VV', 'TM': 'HH'}[pol]
    return np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in res['co_solved_samples'][lab] if f is None or abs(s['frequency_ghz']-f) < 1e-12])

def shell_amp(freq_hz, pol, a, Zs, dphi_deg=0.0):
    """Resistive/impedance circular sheet shell (air both sides), radius a. exp(+jwt)."""
    k = 2*math.pi*freq_hz/C0; x = k*a
    nmax = int(x + 4.05*x**(1/3) + 12)
    d = np.radians(np.atleast_1d(dphi_deg)); f = np.zeros(d.shape, complex)
    for n in range(nmax+1):
        J, Jp, H, Hp = sp.jv(n, x), sp.jvp(n, x), sp.hankel2(n, x), sp.h2vp(n, x)
        # out: J + a H ; in: c J
        if pol == 'TM':   # u cont; k(u'_out - u'_in) = j k eta0/Zs u
            A = np.array([[H, -J], [k*Hp - 1j*k*ETA0/Zs*H, -k*Jp]]); b = np.array([-J, -(k*Jp - 1j*k*ETA0/Zs*J)])
        else:             # u' cont; u_out - u_in = eta0/(j k Zs) * u'
            c = ETA0/(1j*k*Zs)
            A = np.array([[k*Hp, -k*Jp], [H - c*k*Hp, -J]]); b = np.array([-k*Jp, -(J - c*k*Jp)])
        an = np.linalg.solve(A, b)[0]
        f += an*(-1)**n*(1 if n == 0 else 2*np.cos(n*d))
    return -4j*f
