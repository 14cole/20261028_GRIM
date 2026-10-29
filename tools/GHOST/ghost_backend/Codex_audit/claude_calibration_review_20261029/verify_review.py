"""Verify saved review evidence; does not execute solver workloads or change OS settings."""
from pathlib import Path
import hashlib,json,statistics
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STUDY=HERE.parent/'memory_calibration_20261029'
GIB=1024**3

def read(path):return json.loads(path.read_text())
source=read(STUDY/'source_hashes.json')
changed=[name for name,value in source.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value]
assert not changed
historical=read(HERE.parent/'memory_estimation_20261029/input_hashes.json')
changed_history=[name for name,value in historical.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value]
assert not changed_history
study=read(STUDY/'study_summary.json')
assert len(study['runs'])==9
assert all(r['certified'] and all(v==0 for v in r['field_max_absolute_errors'].values()) for r in study['runs'])
validation=read(STUDY/'validation_results.json')
assert all(r['outcome']=='passed' for r in validation)
old=statistics.mean(r['wall_seconds'] for r in study['runs'] if r['name'].startswith('ab_old'))
new=statistics.mean(r['wall_seconds'] for r in study['runs'] if r['name'].startswith('ab_new'))
first=read(HERE.parent/'memory_implementation_20261029/live_inlet15/result.json')['seconds']
events=[json.loads(line) for line in (STUDY/'pressure_hold/pressure_events.jsonl').read_text().splitlines()]
wait=[r for r in events if r['kind'] in ('growth_wait','growth_wait_start')]
initial=events[0]
physical=initial['initial_available_bytes']/GIB
commit=initial['available_commit_bytes']/GIB
workers=[]
for r in study['runs']:
    if r['name'] in ('profile_2','ab_new_1','profile_narrow_8'):
        sample=r['busy_worker_max']
        workers.append(dict(name=r['name'],sampled_busy_private_gib=sample['worker_private']/GIB,
            sum_individual_lifetime_private_peaks_gib=sample['worker_peak_private_sum']/GIB,
            worker_allowance_gib=sample['retained_allowance']/GIB))
original=read(HERE.parent/'memory_implementation_20261029/live_inlet15/request.json')
repeat=read(STUDY/'runs/ab_old_1/request.json')
option_differences={k:[original['options'].get(k),repeat['options'].get(k)]
    for k in original['options'].keys() | repeat['options'].keys()
    if original['options'].get(k)!=repeat['options'].get(k)}
result=dict(reviewed_commit='50d2c64820def24fe9e993cbeef794074fc79998',
    verified_changed_source_files=len(source),source_mismatches=changed,
    verified_historical_files=len(historical),historical_mismatches=changed_history,
    unique_tests=len({r['test'] for r in validation}),reports=len(validation),certified_runs=9,
    timing=dict(first_run_seconds=first,old_ab_mean_seconds=old,new_ab_mean_seconds=new,
        ab_difference_percent=100*(new/old-1),historical_difference_percent=100*(old/first-1),
        identical_geometry_requests=original['request']==repeat['request'],option_differences=option_differences,
        qualification='Cross-session harness/instrumentation differs; background sampler time is not an exclusive wall-time charge.'),
    pressure=dict(initial_available_ram_gib=physical,initial_available_commit_gib=commit,
        inferred_additional_commit_for_physical_binding_gib=physical-commit,
        minimum_observed_limit_gib=min(r['system_commit']['limit_bytes'] for r in events)/GIB,
        maximum_observed_limit_gib=max(r['system_commit']['limit_bytes'] for r in events)/GIB,
        hold_commit_ratio_range=[min(r['system_commit']['committed_bytes']/r['system_commit']['limit_bytes'] for r in wait),
            max(r['system_commit']['committed_bytes']/r['system_commit']['limit_bytes'] for r in wait)],
        qualification='Extra capacity is arithmetic conditional on this snapshot, not a tested pagefile configuration.'),
    workers=workers,
    scope='Read-only verification of saved evidence and source hashes; no new solves, regression suite or OS changes.')
(HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
