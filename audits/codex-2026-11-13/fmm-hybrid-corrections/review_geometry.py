"""Independent checks of Codex's streamed, symmetric and nodal-hybrid near storage (review items 1-4).

usage: python review_checks.py <root> <case>     (one case per process; prints one JSON line)
"""
import json, os, sys, time, resource
import numpy as np
root = os.environ.get("GRIM_ROOT", "/workspace/grim-fmm-followup"); sys.path.insert(0, os.path.join(root, 'tools/GHOST'))
from ghost_backend.twod import operators as op
from ghost_backend.twod.geometry import LinearNode, LinearElement, LinearMesh
from ghost_backend.execution.options import execution_scope, cpu_allocation_scope
from hybrid_galerkin import HybridGalerkin, Cluster, partition

def mesh_from_loops(loops, permute=None):
    """Closed polygons; `permute` renumbers the nodes arbitrarily (node id != geometric order)."""
    total = sum(len(xy) for xy in loops); perm = np.arange(total) if permute is None else np.random.default_rng(permute).permutation(total)
    nodes = [None]*total; elements = []; base = 0
    for li, xy in enumerate(loops):
        m = len(xy)
        for i, p in enumerate(xy): nodes[perm[base+i]] = LinearNode(p, (int(perm[base+i]), 0))
        for i in range(m):
            j = (i+1) % m; v = xy[j]-xy[i]; L = float(np.linalg.norm(v)); t = v/L
            elements.append(LinearElement('body%d' % li, 2, 0, 0, 0, (int(perm[base+i]), int(perm[base+j])), xy[i], xy[j], (xy[i]+xy[j])/2, t, np.array([-t[1], t[0]]), L, len(elements)))
        base += m
    if permute is not None:                       # also shuffle the element order
        order = np.random.default_rng(permute+1).permutation(len(elements))
        elements = [elements[i] for i in order]
        for idx, e in enumerate(elements):
            elements[idx] = LinearElement(e.segment_name, e.seg_type, e.ibc_flag, e.diel_flag, 0, e.node_ids, e.p0, e.p1, e.center, e.tangent, e.normal, e.length, idx) if hasattr(e, 'segment_name') else e
    return LinearMesh(nodes, elements)
def star(n, r=1.): th = -np.linspace(0, 2*np.pi, n, endpoint=False); rr = r*(1+.2*np.cos(5*th)); return np.column_stack((rr*np.cos(th), rr*np.sin(th)))
def circle(n, r=1., c=(0., 0.)): th = -np.linspace(0, 2*np.pi, n, endpoint=False); return np.column_stack((c[0]+r*np.cos(th), c[1]+r*np.sin(th)))
def square(per_side, side=2., grade=0.):
    u = np.linspace(0, 1, per_side, endpoint=False)
    if grade: u = np.where(u < .5, .5*(2*u)**grade, 1-.5*(2*(1-u))**grade)
    h = side/2; c = [(-h, -h), (-h, h), (h, h), (h, -h)]; pts = []
    for a in range(4):
        p, q = np.array(c[a]), np.array(c[(a+1) % 4]); pts.append(p[None, :]+u[:, None]*(q-p)[None, :])
    return np.vstack(pts)
GEOM = {
 'star':            lambda n: [star(n)],
 'two-loops':       lambda n: [circle(n//2, 1., (-1.005, 0.)), circle(n-n//2, 1., (1.005, 0.))],
 'two-loops-tight': lambda n: [circle(n//2, 1., (-1.00005, 0.)), circle(n-n//2, 1., (1.00005, 0.))],
 'concentric':      lambda n: [circle(n//2, 1.), circle(n-n//2, .999)],
 'square':          lambda n: [square(n//4)],
 'square-graded':   lambda n: [square(n//4, grade=3.)],
}
def reference(mesh, k, kind, rows, n):
    ids = np.arange(n)
    if kind == 'W': return op._assemble_linear_hypersingular_matrix(mesh, k, output_node_ids=(rows, ids)).values
    s, d = op._assemble_linear_operator_matrices_multi(mesh, k, kind == 'KP', [None], compute_single_layer=kind == 'S', compute_double_layer=kind != 'S', output_node_ids_many=[(rows, ids)])[0]
    return (s if kind == 'S' else d).values
def matrix(g, kind, n): return np.concatenate([g.apply(np.eye(n, dtype=complex)[:, a:a+48], kind) for a in range(0, n, 48)], axis=1)

