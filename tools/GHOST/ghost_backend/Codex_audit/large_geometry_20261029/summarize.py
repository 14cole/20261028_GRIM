"""Rebuild compact evidence, arithmetic checks and a synthetic-geometry figure."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import numpy as np

from capacity_probe import HERE, ROOT, geometry, save

rows=[]
for path in sorted((HERE/'benchmarks').glob('*/result.json')):
    result=json.loads(path.read_text())
    monitor=json.loads((path.parent/'monitor.json').read_text())
    row={k:result.get(k) for k in ('name','geometry','frequency_ghz','status','solve_seconds','panels','basis_order','options','experimental_preconditioner_tolerance')}
    row.update(peak_tree_rss_gib=monitor['process_tree_peak_rss_bytes']/1024**3,
               peak_tree_private_commit_gib=monitor['process_tree_peak_private_bytes']/1024**3)
    if result['status']=='ok':
        metadata=json.loads((path.parent/'metadata.json').read_text())
        factors=metadata.get('compressed_factors',[])
        row.update(quality_passed=metadata['quality_gate']['passed'], mesh_passed=metadata['mesh_convergence_certified'],
            max_system_unknowns=metadata['dense_largest_system'],
            mesh_max_normalized_complex_difference=metadata['mesh_convergence'].get('complex_max_normalized'),
            stage_seconds=metadata['runtime_profile']['stage_seconds'],
            stage_semantics=metadata['runtime_profile']['stage_semantics'],
            final_mesh_factor_evidence=[dict(unknowns=f['unknowns'], operator=f['compressed'].get('operator'),
                operator_bytes=f['compressed'].get('retained_bytes',f['compressed'].get('bytes')),
                near_bytes=f['compressed'].get('near_bytes'), far_bytes=f['compressed'].get('far_bytes'),
                gmres_columns=f.get('gmres_columns',0), preconditioners=f.get('preconditioners'),
                max_sampled_backward_error=f.get('max_sampled_backward_error'),
                rhs_compression=f.get('sweep_compression')) for f in factors])
    rows.append(row)

comparisons=[]
for reference, other in [('inlet_dense_10g','inlet_compressed_10g'),('airfoil_b256','airfoil_b64'),
    ('high_contrast_compressed_1g','high_contrast_tight_1g'),
    ('high_contrast_compressed_1g_repeat','high_contrast_tight_1g_repeat'),
    ('high_contrast_compressed_1g','high_contrast_compressed_1g_repeat')]:
    a,b=(HERE/'benchmarks'/name/'fields.npz' for name in (reference,other))
    if not a.exists() or not b.exists():continue
    with np.load(a) as x,np.load(b) as y:
        for pol in x.files:
            comparisons.append(dict(reference=reference,other=other,polarization=pol,
                max_normalized_complex_difference=float(np.max(abs(x[pol]-y[pol]))/np.max(abs(x[pol]))),
                all_finite=bool(np.all(np.isfinite(x[pol])) and np.all(np.isfinite(y[pol])))))

baseline=[r for r in rows if r['name'].startswith('high_contrast_compressed_')]
tighter=[r for r in rows if r['name'].startswith('high_contrast_tight_')]
experiment={}
if baseline and tighter:
    before=statistics.median(r['solve_seconds'] for r in baseline)
    after=statistics.median(r['solve_seconds'] for r in tighter)
    experiment=dict(baseline_runs=len(baseline),tighter_runs=len(tighter),baseline_median_seconds=before,
                    tighter_median_seconds=after,seconds_saved=before-after,percent_saved=100*(before-after)/before,
                    baseline_max_rss_gib=max(r['peak_tree_rss_gib'] for r in baseline),
                    tighter_max_rss_gib=max(r['peak_tree_rss_gib'] for r in tighter))
save(HERE/'measurements.json',dict(cases=rows,field_comparisons=comparisons,preconditioner_experiment=experiment,
    memory_note='External 100 ms process-tree sampler. RSS sum may double-count shared pages; private commit is not physical RAM.',
    source_note='Compact compressed_factors metadata covers the final published mesh; runtime stages cover the full certified call.'))

from ghost_backend.compressed.factor import GMRES_RESTART,GMRES_BATCH
from ghost_backend.compressed.tile_processes import WORKER_BYTES
arithmetic=dict(dense_single_matrix_gib={str(n):16*n*n/1024**3 for n in (20000,50000,100000,127000)},
    rhs_workspace_100k_gib={str(b):(32*1024**2+16*12*100000*b)/1024**3 for b in (16,64,256)},
    gmres_basis_100k_16rhs_gib=16*100000*GMRES_BATCH*(GMRES_RESTART+1)/1024**3,
    worker_reservations_gib={str(w):WORKER_BYTES*w/1024**3 for w in (2,4,8)},
    dense_127k_panel_gib={str(width):16*127000*width/1024**3 for width in (4000,8000)},
    electrical_length_wavelengths={str(f):3.6576*f*1e9/299792458 for f in (.1,.3,1,3,10)},
    explanation='Arithmetic bounds or configured allowances, not measured process peaks. Dense matrix excludes LU, original copy and workspaces.')
save(HERE/'memory_arithmetic.json',arithmetic)

sources=['compressed/memory.py','compressed/runtime.py','compressed/hmatrix.py','compressed/hmatrix_factor.py',
    'compressed/inverse.py','compressed/factor.py','compressed/operator.py','compressed/worker_pool.py',
    'compressed/tile_processes.py','compressed/polarization_cache.py','compressed/retained_storage.py',
    'compressed/regional_coefficients.py','execution/options.py','execution/policy.py','execution/selection.py',
    'execution/metrics.py','linalg/dense.py','linalg/hierarchical.py','linalg/refined_lu.py','linalg/residual_spool.py',
    'linalg/sweep.py','twod/adaptivity.py','twod/adaptive_geometry.py','twod/solver.py',
    'twod/assembly/polynomial_pair.py','hpc/twod_driver.py','hpc/scheduler.py']
save(HERE/'source_hashes.json',{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources})

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(3,1,figsize=(10,7.5),layout='constrained')
for ax,name,label in zip(axes,('rectangle','inlet','narrow_inlet'),
    ('Convex control: 30 ft boundary','4 ft deep, 1 ft wide inlet: 38 ft boundary',
     '6 ft deep, 3 inch wide inlet: 42 ft boundary')):
    pairs=geometry(name)['segments'][0]['point_pairs']
    xy=np.array([(p['x1']/12,p['y1']/12) for p in pairs]+[(pairs[-1]['x2']/12,pairs[-1]['y2']/12)])
    ax.fill(xy[:,0],xy[:,1],color='#dce9f4',edgecolor='#205a85',linewidth=2)
    ax.set_aspect('equal');ax.set_xlim(-.3,12.6);ax.set_ylim(-.3,3.3)
    ax.set_title(label,loc='left',fontsize=11);ax.set_xlabel('Length (ft)');ax.set_ylabel('Width (ft)')
    ax.grid(alpha=.2)
fig.suptitle('Synthetic 12 by 3 foot cross-sections used in the audit\nThese are test contours, not a model of the proposed engineering design.',fontsize=12)
fig.savefig(HERE/'test_geometries.png',dpi=170)
plt.close(fig)
print(json.dumps(dict(cases=len(rows),all_completed_cases_pass=all(r.get('quality_passed') and r.get('mesh_passed') for r in rows),
    maximum_field_comparison=max((r['max_normalized_complex_difference'] for r in comparisons),default=None),
    preconditioner_experiment=experiment),indent=2))
