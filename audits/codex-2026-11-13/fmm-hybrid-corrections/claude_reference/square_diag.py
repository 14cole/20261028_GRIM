"""Locate the S/W error of hybrid_nodal on a square (straight sides: K is exactly zero between collinear panels)."""
import sys, json
import numpy as np
if len(sys.argv) > 3 and sys.argv[3] == 'fix':      # trial repair: an operator that is zero on the sampled rows takes the largest scale instead of 1e-300
    import types; src = open('hybrid_galerkin.py').read(); old = "scales=[max(np.linalg.norm(x)*np.sqrt(m/len(sample)),1e-300) for x in v]"
    assert old in src; src = src.replace(old, "scales=[np.linalg.norm(x)*np.sqrt(m/len(sample)) for x in v];scales=[max(s,1e-3*max(scales),1e-300) for s in scales]")
    mod = types.ModuleType('hybrid_galerkin'); mod.__file__ = 'hybrid_galerkin.py'; sys.modules['hybrid_galerkin'] = mod; exec(compile(src, 'hybrid_galerkin_fixed', 'exec'), mod.__dict__)
head = open('review_checks.py').read().split("spec = json.loads")[0]; exec(head)
n0 = int(sys.argv[2]); k = 40+0j; mesh = mesh_from_loops(GEOM['square'](n0), None); n = len(mesh.nodes); out = dict(n=n)
with cpu_allocation_scope(1), execution_scope({'assembly_threads': 1, 'blas_threads': 1}):
    ref = {kind: reference(mesh, k, kind, np.arange(n), n) for kind in ('S', 'K', 'W')}
    for mode in ('stream', 'hybrid_nodal'):
        g = HybridGalerkin(mesh, k, mode=mode, tol=1e-13) if mode != 'stream' else HybridGalerkin(mesh, k, mode=mode)
        out[mode] = {kind: float(np.linalg.norm(matrix(g, kind, n)-ref[kind])/np.linalg.norm(ref[kind])) for kind in ('S', 'K', 'W')}
    # per block: error of the stored factors against the exact block, and the size of the K block
    near = g.near; oracle_g = g.g; rows = []
    from nodal_block import NodalBlock; from hybrid_galerkin import NearOracle
    oracle = NearOracle(mesh, k, 8); bad = 0; comp = 0; worst = []
    # rebuild the partition in the same order to get the panel sets
    member = np.empty(len(g.points), int); member[g.plan.order] = g.plan.leaf_of_point; member = member.reshape(-1, 8)[:, 0]
    panels = [np.flatnonzero(member == i) for i in range(len(g.plan.leaf_start))]; roots = [Cluster(p, oracle_g, 24) for p in panels]; it = iter(near.blocks)
    for i, js in enumerate(g.plan.leaf_neighbors):
        for j in js:
            for a, b, adm in partition(roots[i], roots[j], 1.5):
                r, c, f = next(it)
                if f[0][1] is None: continue
                comp += 1; exact = NodalBlock(oracle, a.ids, b.ids).fetch()
                e = [float(np.linalg.norm(f[z][0]@f[z][1]-exact[z])/max(np.linalg.norm(exact[z]), 1e-300)) for z in range(3)]
                knorm = float(np.linalg.norm(exact[1])/np.linalg.norm(exact[0]))
                if max(e[0], e[2]) > 1e-9: bad += 1; worst.append(dict(shape=exact[0].shape, rank=[f[z][0].shape[1] for z in range(3)], errors=e, K_over_S=knorm))
    out.update(compressed_blocks=comp, bad_blocks=bad, examples=worst[:4], bad_all_have_zero_K=all(w['K_over_S'] < 1e-12 for w in worst))
print(json.dumps(out))
