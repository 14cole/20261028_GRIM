"""Independent checks of Codex's streamed, symmetric and nodal-hybrid near storage (review items 1-4).

usage: python review_checks.py <root> <case>     (one case per process; prints one JSON line)
"""
import json, os, sys, time, resource
import numpy as np
root = sys.argv[1]; sys.path.insert(0, os.path.join(root, 'tools/GHOST'))
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

spec = json.loads(sys.argv[2]); out = dict(spec)
k = complex(*spec.get('k', [40, 0])); mesh = mesh_from_loops(GEOM[spec['geometry']](spec['n']), spec.get('permute')); n = len(mesh.nodes); out['n'] = n
try:
    with cpu_allocation_scope(1), execution_scope({'assembly_threads': 1, 'blas_threads': 1}):
        test = spec['test']
        if test == 'partition':
            g = HybridGalerkin(mesh, k, mode='stream'); geo = g.g
            member = np.empty(len(g.points), int); member[g.plan.order] = g.plan.leaf_of_point; member = member.reshape(-1, 8)[:, 0]
            panels = [np.flatnonzero(member == i) for i in range(len(g.plan.leaf_start))]; P = len(geo.lengths)
            for leaf in spec.get('leaves', [24, 5]):
                roots = [Cluster(p, geo, leaf) for p in panels]; count = np.zeros((P, P), np.int16); expected = np.zeros((P, P), np.int16); adm = 0
                for i, js in enumerate(g.plan.leaf_neighbors):
                    for j in js:
                        expected[np.ix_(panels[i], panels[j])] += 1
                        for a, b, admissible in partition(roots[i], roots[j], 1.5):
                            count[np.ix_(a.ids, b.ids)] += 1; adm += admissible*len(a.ids)*len(b.ids)
                out['leaf%d' % leaf] = dict(exactly_once=bool(np.array_equal(count, expected)), max_count=int(count.max()), expected_max=int(expected.max()),
                                            near_pairs=int(expected.sum()), admissible_fraction=round(adm/max(1, int(expected.sum())), 3), symmetric=bool(np.array_equal(count, count.T)))
        elif test == 'row-batch':
            mats = {}
            for rb in spec['batches']:
                g = HybridGalerkin(mesh, k, mode=spec.get('mode', 'stream'), row_batch=rb)
                mats[rb] = {key: (g.corrections[key].lower if hasattr(g.corrections[key], 'lower') else g.corrections[key]).toarray() for key in ('S', 'K', 'W')}
                out['index_dtype'] = str((g.corrections['K']).indices.dtype); out['K_KP_share'] = bool(np.shares_memory(g.corrections['K'].data, g.corrections['KP'].data))
            first = spec['batches'][0]
            out['max_difference_between_batches'] = {key: float(max(abs(mats[rb][key]-mats[first][key]).max() for rb in spec['batches'])/abs(mats[first][key]).max()) for key in ('S', 'K', 'W')}
        elif test == 'asymmetry':
            a = HybridGalerkin(mesh, k, mode='stream'); b = HybridGalerkin(mesh, k, mode='stream_sym'); res = {}
            for key in ('S', 'W'):
                A = a.corrections[key].toarray(); res[key] = dict(near_asymmetry=float(abs(A-A.T).max()/abs(A).max()))
                full = matrix(a, key, n); sym = matrix(b, key, n); ref = reference(mesh, k, key, np.arange(n), n)
                res[key].update(full_vs_ghost=float(abs(full-ref).max()/abs(ref).max()), symmetric_vs_ghost=float(abs(sym-ref).max()/abs(ref).max()),
                                symmetric_vs_full=float(abs(sym-full).max()/abs(ref).max()), ghost_asymmetry=float(abs(ref-ref.T).max()/abs(ref).max()))
            out['operators'] = res
        elif test == 'matrix':
            t = time.perf_counter(); g = HybridGalerkin(mesh, k, mode=spec['mode'], tol=spec.get('tol', 1e-13), leaf=spec.get('leaf', 24)); out['setup_s'] = round(time.perf_counter()-t, 1)
            out['peak_setup_gib'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20, 3); out['near_bytes_mib'] = round(g.near_bytes/2**20, 1)
            if spec['mode'].startswith('hybrid'):
                h = g.near; out.update(blocks=len(h.blocks), compressed_fraction=round(h.compressed_pairs/max(1, h.covered_pairs), 3), rejections=h.failures,
                                       rank_max=int(max(h.ranks)) if h.ranks else 0, queried_over_near=round(g.queried_pairs/g.near_pairs, 2))
            full = n <= 1700; rows = np.arange(n) if full else np.sort(np.random.default_rng(3).choice(n, 64, replace=False)); errs = {}
            x = np.random.default_rng(5).normal(size=(n, 2))+1j*np.random.default_rng(6).normal(size=(n, 2))
            for kind in ('S', 'K', 'KP', 'W'):
                ref = reference(mesh, k, kind, rows, n)
                errs[kind] = float(abs(matrix(g, kind, n)-ref).max()/abs(ref).max()) if full else float(abs(g.apply(x, kind)[rows]-ref@x).max()/abs(ref@x).max())
            out.update(full_matrix=full, errors=errs, worst=max(errs.values()))
except Exception as exc:
    import traceback; out['error'] = type(exc).__name__+': '+str(exc)[:300]; out['trace'] = traceback.format_exc()[-600:]
print(json.dumps(out), flush=True)
