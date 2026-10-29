"""Verify the latest audit claims without rerunning solves or rewriting prior evidence."""
import hashlib
import json
from pathlib import Path
import statistics
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STUDY=ROOT/'Codex_audit/automatic_selection_20261029'
OLD=ROOT/'Codex_audit/solver_studies_20261029'
sys.path.insert(0,str(ROOT.parent))
from ghost_backend.execution.timing_history import _clean_success
from ghost_backend.twod.constants import DENSE_LINEAR_BACKWARD_ERROR_MAX

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
verified=0
for base in (STUDY,OLD):
    for row in read(base/'evidence_hashes.json'):
        assert sha(base/row['path'])==row['sha256']
        verified+=1
for row in read(STUDY/'changed_files.json'):assert sha(ROOT/row['path'])==row['after_sha256']

history=[]
for folder in sorted((STUDY/'runs').iterdir()):
    if not folder.name.endswith(('_dense','_compressed')):continue
    data=read(folder/'metadata.json');mode=folder.name.rsplit('_',1)[1]
    history.append(dict(run=folder.name,mode=mode,clean_history_eligible=_clean_success(data,mode),
        hierarchical_builds=[dict(builds=f.get('builds'),tighter_rebuilds=f.get('tighter_rebuilds'))
          for rows in data.get('hierarchical_factors',{}).values() for f in rows]))
coating=read(STUDY/'runs/coated3_condition_diagnostic/metadata.json')
systems=coating['experimental_cpu']['systems']
diagnostic=dict(result_status=read(STUDY/'runs/coated3_condition_diagnostic/result.json')['status'],
    exported_quality_passed=coating['quality_gate']['passed'],
    exported_mesh_certified=coating['mesh_convergence_certified'],
    original_gate_failures=sum(not r['gate']['passed'] for r in read(STUDY/'runs/coated3_condition_diagnostic/original_quality_gates.json')),
    recorded_backward_errors=[s['max_backward_error'] for s in systems],
    max_recorded_backward_error=max(s['max_backward_error'] for s in systems),
    release_backward_error_limit=DENSE_LINEAR_BACKWARD_ERROR_MAX,
    max_relative_residual=coating['residual_norm_max'],
    condition_estimator=coating['channel_metadata']['VV']['condition_estimator'],
    condition_estimate=coating['condition_est_max'])
assert diagnostic['result_status']=='diagnostic'
assert diagnostic['exported_quality_passed'] and diagnostic['exported_mesh_certified']
assert diagnostic['original_gate_failures']==8

final_steps=[]
for family in ('dielectric15','narrow15'):
    record=dict(family=family)
    for mode in ('dense','compressed','mixed'):
        values=[read(STUDY/'runs'/f'{family}_r{r}_{mode}'/'metadata.json')['adaptive_mesh']['steps'][-1]['seconds']
                for r in range(2)]
        record[mode]=dict(seconds=values,median_seconds=statistics.median(values))
    final_steps.append(record)
ordinary_mixed=read(OLD/'runs/metal15_auto_budget_6gib/result.json')
ordinary_meta=read(OLD/'runs/metal15_auto_budget_6gib/metadata.json')
output=dict(raw_evidence_files_verified=verified,implementation_hashes_match=True,
    pure_run_history_eligibility=history,coated_diagnostic=diagnostic,final_step_timings=final_steps,
    ordinary_metal_mixed_already_measured=dict(seconds=ordinary_mixed['solve_seconds'],
        ram_budget_gib=ordinary_mixed['options']['ram_budget_gib'],
        backends=[s['backend'] for s in ordinary_meta['adaptive_mesh']['steps']],
        final_step_seconds=ordinary_meta['adaptive_mesh']['steps'][-1]['seconds']),
    reviewed_report_sha256=sha(ROOT/'Claude_audit/review_of_codex_automatic_selection.md'),
    numerical_solves_rerun=False,prior_artifacts_modified=False,production_changes=False)
(HERE/'verification.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
print(json.dumps(output,indent=2))
