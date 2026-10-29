"""Resource-only review: no matrix assembly, factorization, or solver changes."""
import copy
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
from ghost_backend.execution.options import validate_options
from ghost_backend.execution.selection import _forecast_backend

source = ROOT / 'trials/airfoil_matrix_20261027_full/input_airfoil.geo'
original = build_geometry_snapshot(*parse_geometry(source.read_text()))
xs = [p[k] for seg in original['segments'] for p in seg['point_pairs'] for k in ('x1', 'x2')]
chord = max(xs) - min(xs)
scale = 144.0 / chord
scaled = copy.deepcopy(original)
for seg in scaled['segments']:
    for pair in seg['point_pairs']:
        for key in ('x1', 'x2', 'y1', 'y2'):
            pair[key] *= scale

out = dict(original_chord_inches=chord, target_chord_inches=144., scale=scale,
           kind='current-code resource forecast; not a timed solve or accuracy certification',
           angles_assumed=361, threads=4, ram_budget_gib=8., forecasts=[])
cases = [('original', original, 1., 'local'), ('original', original, 10., 'adaptive')]
cases += [('12ft', scaled, freq, strategy) for freq in (0.25, 0.5, 1., 3., 10.)
          for strategy in ('local', 'adaptive')]
for name, geometry, freq, strategy in cases:
    start = time.perf_counter()
    options = validate_options(dict(factorization='adaptive', mesh_strategy=strategy,
                                   basis_order=1, mesh_grading=True, assembly_threads=4,
                                   blas_threads=4, ram_budget_gib=8., compressed_storage_mib=0))
    args = dict(geometry_snapshot=geometry, frequencies_ghz=[freq],
                elevations_deg=list(range(361)), geometry_units='inches', max_panels=100000)
    resources = []
    record = dict(geometry=name, frequency_ghz=freq, mesh_strategy=strategy,
                  certified_candidates=(strategy == 'adaptive'))
    try:
        result = _forecast_backend(args, options, certified=(strategy == 'adaptive'),
                                   resource_records=resources)
        record.update(selected=result['selected'], candidates=result['candidates'])
        record['meshes'] = [{k: row[k] for k in ('phase', 'polarization', 'polynomial_degree',
                                                'panels', 'unknowns', 'formulation', 'backend_peak_gib')}
                            for row in result['meshes']]
    except Exception as exc:
        record['error'] = str(exc)
    record['resource_counts'] = [dict(system_dofs=r['system_dofs'], nodes=r['nodes'],
                                     basis_order=o['basis_order'], formulation=r['formulation'])
                                for r, o in resources]
    record['forecast_seconds'] = time.perf_counter() - start
    out['forecasts'].append(record)
    (Path(__file__).parent / 'size_forecasts.json').write_text(json.dumps(out, indent=2))
    print(json.dumps(record), flush=True)
