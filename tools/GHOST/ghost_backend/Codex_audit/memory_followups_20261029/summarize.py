"""Collate final outcomes without overwriting historical trial evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GIB = 1024**3

def read(path): return json.loads(path.read_text())
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

latest = {}
reports = []
for path in sorted(HERE.glob('validation_results_*.json')):
    rows = read(path)
    for row in rows:
        latest[(row['test'], row['phase'])] = dict(row, report=path.name)
    reports.append(dict(file=path.name, results=len(rows), failures=sum(r['outcome']=='failed' for r in rows)))
assert latest and all(row['outcome']=='passed' for row in latest.values())
runs = []
for name, budget in [('inlet15',6.), ('narrow15',6.), ('dielectric15',8.), ('inlet15_near',4.6)]:
    folder = HERE/('live_'+name)
    result, monitor, metadata = [read(folder/file) for file in ('result.json','monitor.json','metadata.json')]
    assert result['status']=='passed' and result['quality_passed'] and result['mesh_certified']
    assert max(result['relative_max_field_differences'].values()) == 0
    assert monitor['returncode']==0 and monitor['stop_reason'] is None
    events = [json.loads(line) for line in (folder/'events.jsonl').read_text().splitlines()]
    caps = [e['storage_bytes'] for e in events if e['kind']=='automatic_storage']
    plans = [p for p in metadata['experimental_cpu']['memory_estimates'] if 'nonstorage_phase_bytes' in p]
    for plan in plans:
        workspace = max(plan['nonstorage_phase_bytes'].values())
        assert plan['storage_limit_bytes'] == max(0, int(budget*GIB)-workspace)
        assert plan['storage_limit_bytes']+workspace <= int(budget*GIB)
    runs.append(dict(name=name, reservation_gib=budget, seconds=result['seconds'],
        peak_rss_gib=monitor['peak_rss_bytes']/GIB, peak_private_commit_gib=monitor['peak_private_bytes']/GIB,
        storage_min_gib=min(caps)/GIB, storage_max_gib=max(caps)/GIB,
        forecast_peak_gib=max(p['peak_bytes'] for p in plans)/GIB,
        largest_workspace_gib=max(max(p['nonstorage_phase_bytes'].values()) for p in plans)/GIB,
        certified=True, exact_reference_field_match=True))
pressure = []
for label in ('physical_pressure', 'physical_pressure_commit'):
    rows = [json.loads(line) for line in (HERE/(label+'_events.jsonl')).read_text().splitlines()]
    monitor = read(HERE/(label+'_monitor.json'))
    assert monitor['returncode']==0 and monitor['stop_reason'] is None
    checks = [row for row in rows if row['kind']=='checkpoint']
    assert checks and all(row['admitted'] for row in checks)
    start = rows[0]
    pressure.append(dict(label=label, start=start, checkpoints=checks,
        outcome=rows[-1], monitor=monitor,
        highest_observed_numeric_fraction=max(row['observed_payload_fraction'] for row in checks)))
assert pressure[-1]['outcome']['kind']=='complete'
historical = read(HERE.parent/'memory_estimation_20261029/input_hashes.json')
for path, expected in historical.items(): assert digest(ROOT/path)==expected, path
sources = ['execution/memory_budget.py','compressed/memory.py','compressed/runtime.py',
    'twod/solver.py','twod/formulations/thin_layer.py','hpc/scheduler.py','tests/test_memory_followups.py']
summary = dict(status='passed', unique_latest_test_phase_results=len(latest),
    test_files=sorted(set(row['test'].split('::')[0] for row in latest.values())),
    regression_reports=reports, live_runs=runs, physical_pressure_trials=pressure,
    actual_ninety_percent_physical_ram_reached=False,
    historical_input_files_unchanged=len(historical),
    scope_notes=[
        'Physical ramp was capped by measured Windows commit headroom, not 90% physical RAM.',
        'Initial ramp stopped at its guard; revised ramp reserves 64 MiB for allocator metadata and completes at the binding cap.',
        'Overlapping public requests retain the existing numerical BLAS lock; this is not simultaneous factorization throughput evidence.',
        'Some regression runs overlapped representative numerical trials; timings are not controlled performance comparisons.',
        'Early test-only mistakes (missing register kind, barrier inside the BLAS lock, nonexistent test filename) were corrected; latest outcomes are recorded.',
        'Large trials preceded final diagnostic wording and measured-worker reload accounting; focused regressions cover those final changes.',
        'No persistent solve cache, new user option, worker allowance reduction, commit, or push.'])
(HERE/'validation_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
(HERE/'source_hashes.json').write_text(json.dumps({name:digest(ROOT/name) for name in sources}, indent=2)+'\n')
print(json.dumps(dict(status=summary['status'], unique_tests=len(latest), live_runs=runs,
    physical_fraction=max(p['highest_observed_numeric_fraction'] for p in pressure)), indent=2))
