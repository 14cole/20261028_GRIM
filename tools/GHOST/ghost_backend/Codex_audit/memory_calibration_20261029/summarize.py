"""Rebuild the audit summary from saved evidence without rerunning workloads."""
from pathlib import Path
import hashlib,json,statistics
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
GIB=1024**3

def read(path):return json.loads(path.read_text())
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')

def main():
    rows=[]
    names=['ab_old_1','ab_new_1','ab_new_2','ab_old_2','release_4','profile_2','profile_narrow_8','final_inlet_tight','final_dielectric']
    for name in names:
        directory=HERE/'runs'/name
        result=read(directory/'result.json');monitor=read(directory/'monitor.json')
        assert result['status']=='passed' and result['certified'] and monitor['returncode']==0
        assert all(error==0 for error in result['field_max_absolute_errors'].values())
        samples=[json.loads(line) for line in (directory/'samples.jsonl').read_text().splitlines()]
        busy=[sample for sample in samples if sample['busy']]
        rows.append(dict(name=name,wall_seconds=result['wall_seconds'],parent_cpu_seconds=result['parent_cpu_seconds'],
            sampled_family_cpu_seconds=result['sampled_family_cpu_seconds'],
            peak_tree_rss_gib=monitor['peak_tree_rss']/GIB,peak_tree_private_gib=monitor['peak_tree_private']/GIB,
            certified=result['certified'],field_max_absolute_errors=result['field_max_absolute_errors'],
            worker_peaks=result['worker_peaks'],busy_samples=len(busy),
            busy_worker_max={key:max((s[key] for s in busy),default=0) for key in ('worker_uss','worker_private','worker_peak_private_sum','retained_allowance','payload_bytes')},
            instrumentation=result['instrumentation'],sampler_seconds=result['sampler_seconds']))
    old=statistics.mean(row['wall_seconds'] for row in rows if row['name'].startswith('ab_old'))
    new=statistics.mean(row['wall_seconds'] for row in rows if row['name'].startswith('ab_new'))
    validation=read(HERE/'validation_results.json')
    assert not [row for row in validation if row['outcome']!='passed']
    unique={row['test'] for row in validation}
    files=sorted({name.split('::')[0] for name in unique})
    save(HERE/'validation_summary.json',dict(outcomes={'passed':len(unique)},reports=len(validation),test_files=files,
        numerical_trials=len(rows),all_fields_identical=True,
        scope='Combined affected files from both prior audits plus new tests; not the entire repository suite'))
    pressure=[json.loads(line) for line in (HERE/'pressure_events.jsonl').read_text().splitlines()]
    limits=[row['system_commit']['limit_bytes'] for row in pressure if row.get('system_commit')]
    save(HERE/'study_summary.json',dict(runs=rows,ab=dict(old_mean_seconds=old,new_mean_seconds=new,
        difference_percent=100*(new/old-1),order=names[:4],comparison='63429ba versus b233c19; identical native DLLs and monitoring'),
        pressure=dict(monitor=read(HERE/'pressure_monitor.json'),initial_system_commit_limit_gib=limits[0]/GIB,
            minimum_system_commit_limit_gib=min(limits)/GIB,maximum_system_commit_limit_gib=max(limits)/GIB,
            checkpoints=[row for row in pressure if row['kind']=='checkpoint'],
            completion=pressure[-1],scope='Touched allocations; not a complete numerical solve near 90% available RAM')))
    hold=[json.loads(line) for line in (HERE/'pressure_hold/pressure_events.jsonl').read_text().splitlines()]
    assert pressure[-1]['kind']=='complete' and hold[-1]['kind']=='complete'
    hold_limits=[r['system_commit']['limit_bytes'] for r in hold]
    save(HERE/'pressure_hold_summary.json',dict(monitor=read(HERE/'pressure_hold/pressure_monitor.json'),
        minimum_system_commit_limit_gib=min(hold_limits)/GIB,maximum_system_commit_limit_gib=max(hold_limits)/GIB,
        checkpoints=[r for r in hold if r['kind']=='checkpoint'],growth_wait_seconds=10,completion=hold[-1]))
    sources=['compressed/runtime.py','execution/memory.py','execution/memory_budget.py','hpc/scheduler.py','twod/solver.py',
        'tests/test_commit_capacity_growth.py','tests/test_idle_worker_transition.py','tests/test_large_geometry_resources.py','tests/test_request_memory_budget.py']
    save(HERE/'source_hashes.json',{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources})
    historical=read(ROOT/'Codex_audit/memory_estimation_20261029/input_hashes.json')
    changed=[name for name,h in historical.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h]
    assert not changed
    save(HERE/'historical_evidence_verification.json',dict(checked=len(historical),changed=changed))
    print(json.dumps(dict(tests=len(unique),trials=len(rows),ab_percent=100*(new/old-1),
        pressure_checkpoints=[(r['requested_fraction'],r['actual_numeric_fraction']) for r in pressure if r['kind']=='checkpoint']),indent=2))

if __name__=='__main__':main()
