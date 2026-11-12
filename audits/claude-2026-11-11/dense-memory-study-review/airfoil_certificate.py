"""Default adaptive certified airfoil at 3 GHz: certificate flag against quadrature warnings."""
import json, os, sys, time
import numpy as np
root = sys.argv[1]; sys.path.insert(0, os.path.join(root, 'tools/GHOST'))
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
from ghost_backend.twod import solver as S
g = build_geometry_snapshot(*parse_geometry(open(os.path.join(root, 'airfoil.geo')).read()))
angles = [float(x) for x in np.linspace(0, 180, 181)]
t = time.perf_counter()
r = S.solve_monostatic_rcs_2d_certified(g, [3.0], angles, geometry_units='inches', max_panels=200000,
        execution_options=dict(factorization='automatic', mesh_strategy='adaptive', assembly_threads='auto', blas_threads='auto'))
m = r['metadata']
print(json.dumps(dict(wall=round(time.perf_counter()-t, 1), certified=m.get('mesh_convergence_certified'), backend=m.get('linear_backend'),
    polynomial_degree=m.get('polynomial_degree'), panels=m.get('panel_count'), unknowns=m.get('system_unknowns'),
    adaptive={k: v for k, v in (m.get('adaptive_mesh') or {}).items() if k in ('used', 'strategy', 'initial_coarsening', 'fallback')},
    steps=[{k: s.get(k) for k in ('polynomial_degree', 'panels', 'nodes', 'coarsening', 'status')} for s in (m.get('adaptive_mesh') or {}).get('steps', [])],
    warning_count=m.get('warning_count'), warnings=[w[:330] for w in (m.get('warnings') or r.get('warnings') or [])],
    quality=str(m.get('quality_gate') or m.get('quality') or '')[:300]), indent=1, default=str))
