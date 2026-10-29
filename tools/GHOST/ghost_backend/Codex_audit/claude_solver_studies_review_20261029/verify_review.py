"""Read-only source/evidence checks of Claude's solver-studies review."""
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STUDY=ROOT/'Codex_audit/solver_studies_20261029'
sys.path.insert(0,str(ROOT.parent))
from ghost_backend.execution.policy import rank_candidates,relative_cost
from ghost_backend.execution.timing_history import adjust

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def meta(name):return read(STUDY/'runs'/name/'metadata.json')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

manifest=read(STUDY/'evidence_hashes.json')
assert all(sha(STUDY/row['path'])==row['sha256'] for row in manifest)
rows=[]
for family,repeats in [('metal15',3),('narrow15',2)]:
    for index in (2,3):
        selection=meta(f'{family}_r0_adaptive')['adaptive_mesh']['steps'][index]['backend_selection']
        candidates=selection['candidates']
        measured={mode:[meta(f'{family}_r{repeat}_{mode}')['adaptive_mesh']['steps'][index]['seconds']
                         for repeat in range(repeats)] for mode in ('dense','compressed')}
        medians={mode:statistics.median(values) for mode,values in measured.items()}
        assert rank_candidates(candidates,selection['admission_budget_gib'])[0]==selection['selected']
        rows.append(dict(shape=family,step=index+1,unknowns=selection['meshes'][0]['unknowns'],
            predicted_ratio=candidates['dense']['cost']/candidates['compressed']['cost'],
            measured_seconds=measured,median_seconds=medians,measured_ratio=medians['dense']/medians['compressed'],
            selected=selection['selected'],reason=selection['reason']))

dense=meta('capacity_inlet_dielectric_15ghz')
compressed=meta('dielectric15_compressed_probe')
selection=dense['backend_selection']
steps=dense['adaptive_mesh']['steps']
assert all(s['backend_selection']['forecast_reused'] for s in steps)
assert steps[0]['backend_selection']['candidates']==steps[1]['backend_selection']['candidates']
per_degree=[]
for degree in (2,3):
    costs={mode:sum(relative_cost(row['resources'],361,mode,4,4)
               for row in selection['meshes'] if row['polynomial_degree']==degree)
           for mode in ('dense','compressed')}
    per_degree.append(dict(degree=degree,costs=costs,ratio=costs['dense']/costs['compressed']))
dielectric=dict(reused_scope=steps[-1]['backend_selection']['mesh_forecast_scope'],
    aggregate_predicted_ratio=selection['candidates']['dense']['cost']/selection['candidates']['compressed']['cost'],
    recomputed_individual_mesh_priors=per_degree,
    measured_steps={mode:[s['seconds'] for s in data['adaptive_mesh']['steps']]
                    for mode,data in [('dense',dense),('compressed',compressed)]},
    final_compressed_hints=[f.get('preconditioner_hint') for f in compressed['compressed_factors']],
    arithmetic_mixed_seconds=steps[0]['seconds']+compressed['adaptive_mesh']['steps'][1]['seconds'],
    arithmetic_only_not_observed=True)

# No solves and no timing-cache read/write: injected measurements isolate ranking semantics.
candidates=dict(dense=dict(cost=100.,peak_gb=4.),compressed=dict(cost=1.,peak_gb=2.,hmatrix=True))
synthetic=dict(candidates=candidates,selected='dense',admission_budget_gib=12.)
stamp=time.time()-1
measured=adjust(synthetic,'audit',entries={'audit':{
    'dense':[[stamp,100.],[stamp,100.]],'compressed':[[stamp,1.],[stamp,1.]]}})
assert measured['selected']=='dense' and measured['candidates']['compressed']['cost']==1.
plain={m:dict(c) for m,c in candidates.items()}
plain['compressed'].pop('hmatrix')
assert rank_candidates(plain,12.)[0]=='compressed'
ranking=dict(hmatrix_order=rank_candidates(candidates,12.),
    without_hmatrix_order=rank_candidates(plain,12.),
    injected_timing_adjustment=dict(selected=measured['selected'],reason=measured['reason'],
        timing_model=measured['timing_model']),
    scope='Synthetic unit-sized ranking probe, not a solver performance measurement.')
output=dict(evidence_files_verified=len(manifest),metal_steps=rows,dielectric=dielectric,ranking_probe=ranking,
    source_hashes={name:sha(ROOT/name) for name in ['execution/policy.py','execution/selection.py',
        'execution/timing_history.py','twod/adaptivity.py','compressed/preconditioner_hints.py']},
    reviewed_report_sha256=sha(ROOT/'Claude_audit/review_of_codex_solver_studies.md'),
    numerical_solves_rerun=False,production_changes=False)
(HERE/'verification.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
print(json.dumps(output,indent=2))
