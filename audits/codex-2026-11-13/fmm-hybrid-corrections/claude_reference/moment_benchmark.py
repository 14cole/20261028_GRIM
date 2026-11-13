"""Panel-moment adapter against Codex's streamed point adapter, same mesh, fresh process per case.
usage: python moment_benchmark.py '<json: n, k, mode (moment|stream|stream_moment_tree), shape>'
"""
import json, os, resource, sys, time
import numpy as np
sys.path.insert(0, os.environ['GRIM_ROOT']+'/tools/GHOST')
from ghost_backend.execution.options import cpu_allocation_scope, execution_scope
from ghost_backend.twod import operators as op
from fmm_galerkin import circle_mesh
spec = json.loads(sys.argv[1]); n = spec['n']; k = complex(*spec.get('k', [40, 0])); mode = spec['mode']
mesh = circle_mesh(n, star=spec.get('shape', 'star') == 'star', inward=True)
rng = np.random.default_rng(20261113); x = rng.normal(size=(n, 2))+1j*rng.normal(size=(n, 2))
rss = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20
with cpu_allocation_scope(1), execution_scope({'assembly_threads': 1, 'blas_threads': 1}):
    t = time.perf_counter()
    if mode == 'moment':
        from moment_galerkin import MomentGalerkin
        g = MomentGalerkin(mesh, k); far_bytes = g.far.bytes; phase_bytes = sum(a.nbytes for a in (g.far.source, g.far.target, g.far.sdotn) if a is not None); levels = g.far.plan.levels; direct = g.far.direct
    else:
        from hybrid_galerkin import HybridGalerkin
        g = HybridGalerkin(mesh, k, mode='stream'); far_bytes = g.plan.bytes; phase_bytes = g.plan.E.nbytes+g.plan.Eout.nbytes+g.plan.dip.nbytes; levels = g.plan.levels; direct = bool(g.plan.low_frequency_direct)
    setup = time.perf_counter()-t; peak_setup = rss(); times = {}; ys = {}
    for kind in ('S', 'K', 'KP', 'W'):
        ts = []
        for _ in range(3):
            t = time.perf_counter(); g.apply(x[:, 0], kind); ts.append(time.perf_counter()-t)
        times[kind] = sorted(ts)[1]; ys[kind] = g.apply(x, kind)
    peak_products = rss()
    rows = np.sort(rng.choice(n, 32, replace=False)); ids = np.arange(n); errors = {}
    for kind in ('S', 'K', 'KP', 'W'):
        if kind == 'W': ref = op._assemble_linear_hypersingular_matrix(mesh, k, output_node_ids=(rows, ids)).values
        else:
            s, d = op._assemble_linear_operator_matrices_multi(mesh, k, kind == 'KP', [None], compute_single_layer=kind == 'S', compute_double_layer=kind != 'S', output_node_ids_many=[(rows, ids)])[0]; ref = (s if kind == 'S' else d).values
        errors[kind] = float(abs(ys[kind][rows]-ref@x).max()/abs(ref@x).max())
    if spec.get('out'): np.savez_compressed(spec['out'], **{'y_'+kd: v for kd, v in ys.items()}, x=x)
print(json.dumps(dict(spec, setup_s=round(setup, 2), kernel_s=round(getattr(g, 'kernel_seconds', 0), 2), levels=levels, all_near=direct, near_pairs=int(g.near_pairs), retained_mib=round(g.retained_bytes/2**20, 2),
    far_mib=round(far_bytes/2**20, 2), phase_tables_mib=round(phase_bytes/2**20, 2), near_mib=round(g.near_bytes/2**20, 2), peak_setup_gib=round(peak_setup, 3), peak_products_gib=round(peak_products, 3),
    product_ms={kd: round(1e3*v, 2) for kd, v in times.items()}, sampled_errors=errors)))
