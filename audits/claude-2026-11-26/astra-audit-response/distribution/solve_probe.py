"""Run inside a (possibly degraded) tools/GHOST copy on PYTHONPATH: small 2D solves; report everything a user could see."""
import json, sys, time, warnings, logging, io
import numpy as np
log = io.StringIO(); logging.basicConfig(stream=log, level=logging.DEBUG)
caught = []
warnings.simplefilter('always')
_show = warnings.showwarning
warnings.showwarning = lambda m, c, f, l, *a, **k: caught.append(f'{c.__name__}: {m} ({f}:{l})')
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
from ghost_backend.execution.options import cpu_allocation_scope
from ghost_backend.twod.solver import solve_monostatic_rcs_2d
from ghost_backend.twod.assembly.native import far, near, table

def geometry(typ, panels, radius=0.08):
    theta = -2*np.pi*np.arange(panels)/panels
    pts = radius*np.column_stack((np.cos(theta), np.sin(theta)*0.6))   # ellipse, not Codex's circle
    lines = ['Title: ellipse', f'Segment: body {typ}', f'properties: {typ} 1 0 {int(typ == 3)} 0']
    lines += [' '.join(f'{v:.17g}' for v in (*a, *b)) for a, b in zip(pts, np.roll(pts, -1, axis=0))]
    lines += ['IBCS_Resistances:', '', 'Dielectrics:'] + (['1 3.0 -0.1 1.0 0.0'] if typ == 3 else [])
    return build_geometry_snapshot(*parse_geometry('\n'.join(lines)+'\n'))

def walk(obj, path=''):
    """Every metadata entry whose key or string value mentions native/fallback/slow/backend."""
    hits = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f'{path}/{k}'
            if any(w in str(k).lower() for w in ('native', 'fallback', 'slow', 'backend', 'warning', 'speed')):
                hits[p] = v if isinstance(v, (str, int, float, bool, type(None))) else json.loads(json.dumps(v, default=str))[:5] if isinstance(v, list) else str(v)[:300]
            hits.update(walk(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:3]): hits.update(walk(v, f'{path}[{i}]'))
    return hits

out = dict(loaders=dict(far_dll=far._dll() is not None, far_block=far.library() is not None if hasattr(far, 'library') else None,
                        scatter=far.scatter_library() is not None, tile=far.tile_library() is not None,
                        near_dll=near._dll() is not None, near_available=bool(near.available()),
                        table=table.library() is not None), runs=[])
fields = {}
for name, typ, panels, method in (('pec_dense', 2, 384, 'dense'), ('diel_dense', 3, 384, 'dense'), ('diel_compressed', 3, 384, 'compressed')):
    opts = dict(factorization=method, basis_order=1, mesh_strategy='global', assembly_threads=1, blas_threads=1,
                rhs_compression='off', ram_budget_gib=3)
    t = time.perf_counter()
    with cpu_allocation_scope(1):
        r = solve_monostatic_rcs_2d(geometry(typ, panels), [2.0], list(range(0, 180, 6)), geometry_units='meters',
                                    strict_quality_gate=True, execution_options=opts)
    wall = time.perf_counter()-t
    meta = r['metadata']
    for pol, rows in r['co_solved_samples'].items():
        fields[f'{name}_{pol}'] = np.array([complex(x['rcs_amp_real'], x['rcs_amp_imag']) for x in rows])
    out['runs'].append(dict(name=name, wall_s=round(wall, 3), linear_backend=meta.get('linear_backend'),
                            quality_passed=meta['quality_gate']['passed'], metadata_warnings=meta.get('warnings'),
                            response_warnings=r.get('warnings'), metadata_hits=walk(meta)))
np.savez(sys.argv[1], **fields)
out['python_warnings'] = caught; out['logging_output'] = log.getvalue()[-2000:]
out['top_level_metadata_keys'] = sorted(meta)
print(json.dumps(out, indent=1, default=str))
