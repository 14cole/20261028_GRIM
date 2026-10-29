"""Verify final regression outcomes, real trials and preserved historical inputs."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
GIB=1024**3


def read(path):return json.loads(path.read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


latest={}
test_runs=[]
for path in sorted(HERE.glob('validation_results_*.json')):
    rows=read(path)
    for row in rows:latest[(row['test'],row['phase'])]=dict(row,report=path.name)
    test_runs.append(dict(file=path.name,reported=len(rows),failures=sum(r['outcome']=='failed' for r in rows)))
assert latest and all(row['outcome']=='passed' for row in latest.values())
runs=[]
for name,budget in [('inlet15',6.),('narrow15',6.),('dielectric15',8.)]:
    folder=HERE/('live_'+name)
    result,monitor,metadata=[read(folder/file) for file in ('result.json','monitor.json','metadata.json')]
    assert result['status']=='passed' and result['quality_passed'] and result['mesh_certified']
    assert max(result['relative_max_field_differences'].values())==0
    assert monitor['returncode']==0 and monitor['stop_reason'] is None
    events=[json.loads(line) for line in (folder/'events.jsonl').read_text().splitlines()]
    caps=[e['storage_bytes'] for e in events if e['kind']=='automatic_storage']
    assert min(caps)==max(caps)==int(.6*budget*GIB),(name,min(caps),max(caps))
    assert metadata['memory_accounting']['checks']
    runs.append(dict(name=name,reservation_gib=budget,seconds=result['seconds'],
        peak_rss_gib=monitor['peak_rss_bytes']/GIB,peak_private_commit_gib=monitor['peak_private_bytes']/GIB,
        automatic_storage_gib=min(caps)/GIB,storage_cap_reads=len(caps),
        exact_reference_field_match=True,certified=True))
historical=read(HERE.parent/'memory_estimation_20261029/input_hashes.json')
for path,expected in historical.items():assert digest(ROOT/path)==expected,path
sources=['execution/memory_budget.py','execution/memory.py','execution/options.py',
    'execution/angle_batch.py','execution/cpu.py','execution/frequency_sweep.py',
    'execution/diagnostics.py','execution/timing_history.py','twod/solver.py',
    'twod/adaptivity.py','compressed/runtime.py','compressed/factor.py',
    'compressed/hmatrix.py','compressed/operator.py','compressed/polarization_cache.py',
    'compressed/retained_storage.py','compressed/worker_pool.py','hpc/scheduler.py',
    'hpc/twod_driver.py','runs/local_twod_driver.py','tests/test_request_memory_budget.py',
    'tests/test_memory_safety.py']
summary=dict(status='passed',unique_latest_test_phase_results=len(latest),
    test_files=sorted(set(row['test'].split('::')[0] for row in latest.values())),
    test_runs=test_runs,live_runs=runs,historical_input_files_unchanged=len(historical),
    physical_ninety_percent_stress_test=False,
    notes=['Controlled 70/80/85/90 percent admission tests pass; real runs use 6/8 GiB reservations.',
           'One restricted-process worker-queue test was interrupted; isolated and broad unrestricted reruns passed.',
           'A spawned driver initially lacked PYTHONPATH; audit harness corrected and that test passed on rerun.',
           'A mistyped test filename collected no tests; corrected before the successful suites.',
           'Worker growth allowances and the 60 percent automatic payload share remain conservative; no unsupported calibration reduction.'])
(HERE/'validation_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
(HERE/'source_hashes.json').write_text(json.dumps({name:digest(ROOT/name) for name in sources},indent=2)+'\n')
print(json.dumps(dict(status=summary['status'],unique_tests=summary['unique_latest_test_phase_results'],live_runs=runs),indent=2))
