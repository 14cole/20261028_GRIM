"""Independent correctness checks of Codex's reusable Galerkin operators (CachedGalerkin).

Every operator (S, K, K', W) is compared with GHOST's own assembled matrix: the complete matrix when
n <= 1600, otherwise 96 sampled rows applied to two random vectors. Geometries include cases the
handoff did not cover: corners, graded and nonuniform panels, close bodies, extreme aspect ratio, low k.
usage: python operator_checks.py <root> [case ...]
"""
import json, math, os, sys, time, traceback
import numpy as np
root = sys.argv[1]; sys.path.insert(0, os.path.join(root, 'tools/GHOST'))
from ghost_backend.twod import operators as op
from ghost_backend.twod.geometry import LinearNode, LinearElement, LinearMesh
from ghost_backend.execution.options import execution_scope, cpu_allocation_scope
from cached_galerkin import CachedGalerkin

def mesh_from_loops(loops):
    """loops: list of (m,2) vertex arrays, each a closed polygon traversed so that the normal (-t_y, t_x) is consistent."""
    nodes, elements, base = [], [], 0
    for li, xy in enumerate(loops):
        m = len(xy)
        for i, p in enumerate(xy): nodes.append(LinearNode(p, (base + i, 0)))
        for i in range(m):
            j = (i + 1) % m; v = xy[j] - xy[i]; length = float(np.linalg.norm(v)); t = v / length
            elements.append(LinearElement('body%d' % li, 2, 0, 0, 0, (base + i, base + j), xy[i], xy[j], (xy[i] + xy[j]) / 2, t, np.array([-t[1], t[0]]), length, len(elements)))
        base += m
    return LinearMesh(nodes, elements)

def circle(n, r=1., c=(0., 0.), warp=0.):
    s = np.linspace(0, 1, n, endpoint=False); th = 2*np.pi*(s + warp*np.sin(2*np.pi*s)/(2*np.pi))     # warp < 1 gives nonuniform panels
    return np.column_stack((c[0] + r*np.cos(th), c[1] + r*np.sin(th)))
def star(n, r=1.): th = np.linspace(0, 2*np.pi, n, endpoint=False); rr = r*(1 + .2*np.cos(5*th)); return np.column_stack((rr*np.cos(th), rr*np.sin(th)))
def ellipse(n, a, b): th = np.linspace(0, 2*np.pi, n, endpoint=False); return np.column_stack((a*np.cos(th), b*np.sin(th)))
def square(per_side, side=2., grade=0.):
    u = np.linspace(0, 1, per_side, endpoint=False)
    if grade: u = .5*(1 - np.cos(np.pi*u))**1.0 if grade == 1 else (np.where(u < .5, .5*(2*u)**grade, 1 - .5*(2*(1-u))**grade))
    h = side/2; c = [(-h, -h), (h, -h), (h, h), (-h, h)]; pts = []
    for a in range(4):
        p, q = np.array(c[a]), np.array(c[(a+1) % 4]); pts.append(p[None, :] + u[:, None]*(q - p)[None, :])
    return np.vstack(pts)

CASES = {
 'star-real':            (lambda: [star(1500)], 60+0j),
 'star-lossy':           (lambda: [star(1500)], 60-1j),
 'star-high-k':          (lambda: [star(4000)], 160+0j),
 'star-lossy-high-k':    (lambda: [star(4000)], 160-8j),
 'circle-nonuniform':    (lambda: [circle(1500, warp=.85)], 60+0j),
 'square-uniform':       (lambda: [square(350)], 40+0j),
 'square-graded':        (lambda: [square(380, grade=3.)], 40+0j),
 'two-circles-gap-1e-2': (lambda: [circle(700, 1., (-1.005, 0.)), circle(700, 1., (1.005, 0.))], 40+0j),
 'two-circles-gap-1e-4': (lambda: [circle(700, 1., (-1.00005, 0.)), circle(700, 1., (1.00005, 0.))], 40+0j),
 'concentric-gap-1e-3':  (lambda: [circle(750, 1.), circle(750, .999)], 50+0j),
 'ellipse-20-to-1':      (lambda: [ellipse(1500, 2., .1)], 40+0j),
 'low-k-0.5':            (lambda: [star(256)], .5+0j),
 'low-k-3':              (lambda: [star(256)], 3+0j),
 'low-k-12-all-near':    (lambda: [star(800)], 12+0j),
 'two-level-no-fallback': (lambda: [star(900)], 22+0j),
 'level-transition-2-3a': (lambda: [star(1000)], 31+0j),
 'level-transition-2-3b': (lambda: [star(1000)], 32.5+0j),
 'level-transition-3-4a': (lambda: [star(1500)], 62+0j),
 'level-transition-3-4b': (lambda: [star(1500)], 65.5+0j),
 'fine-mesh-fixed-k':    (lambda: [star(4000)], 40+0j),
}
names = sys.argv[2:] or list(CASES)
rng = np.random.default_rng(7)
for name in names:
    build, k = CASES[name]; row = dict(case=name, k=[k.real, k.imag])
    try:
        mesh = mesh_from_loops(build()); n = len(mesh.nodes); lengths = np.array([e.length for e in mesh.elements])
        row.update(n=n, panel_kl_max=float(abs(k)*lengths.max()), panel_ratio=float(lengths.max()/lengths.min()))
        with cpu_allocation_scope(1), execution_scope({'assembly_threads': 1, 'blas_threads': 1}):
            t = time.perf_counter(); g = CachedGalerkin(mesh, k); row.update(setup_s=round(time.perf_counter()-t, 2), levels=g.plan.levels,
                low_frequency_direct=bool(g.plan.low_frequency_direct), near_panel_pairs=int(g.near_pairs), near_fraction=round(g.near_pairs/len(lengths)**2, 4))
            full = n <= 1600
            rows = np.arange(n) if full else np.sort(rng.choice(n, 96, replace=False)); cols = np.arange(n)
            x = np.eye(n, dtype=complex) if full else rng.normal(size=(n, 2)) + 1j*rng.normal(size=(n, 2))
            errors = {}
            for kind in ('S', 'K', 'KP', 'W'):
                if kind == 'W': ref = op._assemble_linear_hypersingular_matrix(mesh, k, output_node_ids=(rows, cols)).values
                else:
                    s, d = op._assemble_linear_operator_matrices_multi(mesh, k, kind == 'KP', [None], compute_single_layer=kind == 'S', compute_double_layer=kind != 'S', output_node_ids_many=[(rows, cols)])[0]
                    ref = (s if kind == 'S' else d).values
                # apply in bounded column chunks: expansion scratch grows with the number of columns
                y = np.concatenate([g.apply(x[:, c:c+48], kind)[rows] for c in range(0, x.shape[1], 48)], axis=1); target = ref if full else ref @ x
                errors[kind] = float(np.max(abs(y - target))/np.max(abs(target)))
            row.update(full_matrix=full, errors=errors, worst=max(errors.values()))
    except Exception as exc:
        row.update(error=type(exc).__name__ + ': ' + str(exc)[:200])
    print(json.dumps(row), flush=True)
