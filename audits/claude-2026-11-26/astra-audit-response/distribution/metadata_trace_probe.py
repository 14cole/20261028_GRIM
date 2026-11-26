"""Does any result metadata distinguish native from fallback 2D assembly?  Full-text search of the metadata JSON, plus near-call counts."""
import json, sys, numpy as np
sys.argv = [sys.argv[0], '/dev/null']
from ghost_backend.twod.assembly.native import near, far, table
from ghost_backend.twod import operators
calls = dict(box_arguments=0)
_orig = near.box_arguments
def counted(*a, **k):
    calls['box_arguments'] += 1; return _orig(*a, **k)
near.box_arguments = counted
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
from ghost_backend.execution.options import cpu_allocation_scope
from ghost_backend.twod.solver import solve_monostatic_rcs_2d
theta = -2*np.pi*np.arange(384)/384
pts = 0.08*np.column_stack((np.cos(theta), 0.6*np.sin(theta)))
lines = ['Title: e', 'Segment: body 3', 'properties: 3 1 0 1 0'] + [' '.join(f'{v:.17g}' for v in (*a, *b)) for a, b in zip(pts, np.roll(pts, -1, axis=0))] + ['IBCS_Resistances:', '', 'Dielectrics:', '1 3.0 -0.1 1.0 0.0']
with cpu_allocation_scope(1):
    r = solve_monostatic_rcs_2d(build_geometry_snapshot(*parse_geometry('\n'.join(lines)+'\n')), [2.0], [0, 45], geometry_units='meters',
        strict_quality_gate=True, execution_options=dict(factorization='dense', basis_order=1, mesh_strategy='global', assembly_threads=1, blas_threads=1, rhs_compression='off', ram_budget_gib=3))
text = json.dumps(r['metadata'], default=str)
found = {}
def walk(o, p=''):
    if isinstance(o, dict):
        for k, v in o.items(): walk(v, p+'/'+str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o[:2]): walk(v, f'{p}[{i}]')
    elif isinstance(o, str) and any(w in o for w in ('native', 'horner', 'ppoly', 'numpy')): found[p] = o
walk(json.loads(text))
print(json.dumps(dict(loaders=dict(near=near.available(), far=far._dll() is not None, tile=far.tile_library() is not None, table=table.library() is not None),
                      near_box_argument_calls=calls['box_arguments'], metadata_strings_naming_an_assembly_route=found), indent=1))
