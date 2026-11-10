import sys, math, time, warnings
sys.path.insert(0, '/home/user/20261028_GRIM/tools/GHOST')
import numpy as np
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
from ghost_backend.bor import dispatch as D
from ghost_backend.validation import sphere as SP
C0=299792458.0
def snap(text):
    t, s, i, d = parse_geometry(text)
    return build_geometry_snapshot(t, s, i, d)
def arc_rows(a, n, z0=0.0, flip=False):
    th = np.linspace(0, np.pi, n+1)
    rho = a*np.sin(th); z = z0 + a*np.cos(th); rho[0]=0; rho[-1]=0
    return '\n'.join(f'{rho[i]:.15g} {z[i]:.15g} {rho[i+1]:.15g} {z[i+1]:.15g}' for i in range(n))
def rows(pts):
    return '\n'.join(f'{pts[i][0]:.15g} {pts[i][1]:.15g} {pts[i+1][0]:.15g} {pts[i+1][1]:.15g}' for i in range(len(pts)-1))
def geo(segs, ibc='', diel=''):
    """segs: list of (name, typ, props, rowtext)"""
    s = "Title: t\n"
    for name, typ, props, r in segs:
        s += f"Segment: {name} {typ}\nproperties: {props}\n{r}\n"
    s += f"IBCS_Resistances:\n{ibc}\nDielectrics:\n{diel}\n"
    return snap(s)
def sphere(a, n, kind='pec', N=1, zs=None, eps=None, mu=1.0, z0=0.0):
    if kind=='pec': return geo([('b',2,f'2 {N} 0 0 0',arc_rows(a,n,z0))])
    if kind=='ibc': return geo([('b',2,f'2 {N} 10 0 0',arc_rows(a,n,z0))], ibc=f'10 constant {zs.real} {zs.imag} 0 0')
    if kind=='sheet': return geo([('b',1,f'1 {N} 10 0 0',arc_rows(a,n,z0))], ibc=f'10 constant {zs.real} {zs.imag} 0 0')
    if kind=='diel':
        eps=complex(eps); mu=complex(mu)
        return geo([('b',3,f'3 {N} 0 1 0',arc_rows(a,n,z0))], diel=f'1 {eps.real} {eps.imag} {mu.real} {mu.imag}')
def coated(b, a, n, eps, mu=1.0, N=1, nc=None):
    eps=complex(eps); mu=complex(mu)
    return geo([('o',3,f'3 {N} 0 1 0',arc_rows(a,n)),('c',4,f'4 {N} 0 1 0',arc_rows(b,nc or n))], diel=f'1 {eps.real} {eps.imag} {mu.real} {mu.imag}')
def run(g, f, asp, **kw):
    kw.setdefault('workers', 2); kw.setdefault('geometry_units','meters')
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        r = D.solve_monostatic_rcs_bor(g, [f] if np.isscalar(f) else list(f), list(asp), **kw)
    return r
def chan(r, pol, fi=None):
    ss = r['co_solved_samples'][pol]
    return (np.array([s['rcs_linear'] for s in ss]), np.array([s['rcs_amp_real']+1j*s['rcs_amp_imag'] for s in ss]))
def db(x): return 10*np.log10(np.maximum(x,1e-300))
def f_for_ka(ka, a): return ka*C0/(2*np.pi*a)/1e9
