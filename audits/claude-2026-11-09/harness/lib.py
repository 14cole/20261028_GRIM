import sys, math, time
sys.path.insert(0, '/home/user/20261028_GRIM/tools/GHOST')
import numpy as np
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot

def snap(text):
    t, s, i, d = parse_geometry(text)
    return build_geometry_snapshot(t, s, i, d)

def circle_rows(a, n, cw=True, x0=0.0, y0=0.0):
    th = np.linspace(0, 2*np.pi, n+1)
    if cw: th = -th
    # area-preserving polygon radius
    r = a*math.sqrt((2*math.pi/n)/math.sin(2*math.pi/n))
    x = x0 + r*np.cos(th); y = y0 + r*np.sin(th)
    return '\n'.join(f'{x[i]:.15g} {y[i]:.15g} {x[i+1]:.15g} {y[i+1]:.15g}' for i in range(n))

def circle_geo(a, n, props='2 1 0 0 0', typ=2, ibc='', diel='', extra=''):
    return snap(f"Title: c\nSegment: body {typ}\nproperties: {props}\n{circle_rows(a,n)}\n{extra}\nIBCS_Resistances:\n{ibc}\nDielectrics:\n{diel}\n")

def bor_sphere(a, n, props='2 1 0 0 0', typ=2, ibc='', diel=''):
    th = np.linspace(0, np.pi, n+1)
    rho = a*np.sin(th); z = a*np.cos(th); rho[0]=0; rho[-1]=0
    rows = '\n'.join(f'{rho[i]:.15g} {z[i]:.15g} {rho[i+1]:.15g} {z[i+1]:.15g}' for i in range(n))
    return snap(f"Title: s\nSegment: body {typ}\nproperties: {props}\n{rows}\nIBCS_Resistances:\n{ibc}\nDielectrics:\n{diel}\n")
