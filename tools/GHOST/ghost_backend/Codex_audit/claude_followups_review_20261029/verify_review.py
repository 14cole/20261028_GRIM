"""Read-only verification of saved runs and Claude's follow-up review."""
from collections import Counter
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AUDIT = HERE.parent
GIB = 1024**3

def read(path): return json.loads(path.read_text())
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

cases = []
for case in ('inlet15', 'narrow15', 'dielectric15'):
    records = []
    for folder in ('memory_implementation_20261029', 'memory_followups_20261029'):
        path = AUDIT/folder/('live_'+case)
        result, metadata = read(path/'result.json'), read(path/'metadata.json')
        assert result['status']=='passed' and max(result['relative_max_field_differences'].values())==0.
        profile = metadata['runtime_profile']
        samples = metadata['memory_accounting']['worker_samples']
        events = [json.loads(line) for line in (path/'events.jsonl').read_text().splitlines()]
        counts = Counter(e.get('event',{}).get('stage_key') for e in events)
        records.append(dict(evidence_folder=folder, seconds=result['seconds'],
            spool_write_calls=profile['stage_calls'].get('compressed_spool_write',0),
            spool_write_seconds=profile['stage_seconds'].get('compressed_spool_write',0),
            spool_read_calls=profile['stage_calls'].get('compressed_spool_read',0),
            spool_read_seconds=profile['stage_seconds'].get('compressed_spool_read',0),
            spool_write_progress_notifications=counts['compressed_spool_write'],
            stage_seconds=profile['stage_seconds'], stage_semantics=profile['stage_semantics'],
            retained_worker_samples=len(samples),
            maximum_saved_worker_uss_gib=max([s.get('unique_resident_bytes',0) for s in samples],default=0)/GIB,
            maximum_saved_worker_private_gib=max([s.get('private_bytes',0) for s in samples],default=0)/GIB))
    assert records[0]['spool_write_calls']==records[1]['spool_write_calls']
    cases.append(dict(case=case, records=records,
        slowdown_percent=100*(records[1]['seconds']/records[0]['seconds']-1)))
previous = read(AUDIT/'memory_implementation_20261029/validation_summary.json')
current = read(AUDIT/'memory_followups_20261029/validation_summary.json')
source_hashes = read(AUDIT/'memory_followups_20261029/source_hashes.json')
for name, expected in source_hashes.items(): assert digest(ROOT/name)==expected, name
paths = ['Claude_audit/review_of_codex_memory_followups.md', 'execution/memory_budget.py',
    'execution/metrics.py', 'compressed/memory.py', 'compressed/runtime.py',
    'compressed/worker_pool.py', 'compressed/tile_processes.py', 'ui/solver.py']
out = dict(reviewed_commit='b233c192fa779be738f2e418172e84a5fc3460aa',
    saved_source_hashes_match=True, timing_and_spooling=cases,
    previous_test_phase_results=previous['unique_latest_test_phase_results'],
    current_test_phase_results=current['unique_latest_test_phase_results'],
    previous_only_test_files=sorted(set(previous['test_files'])-set(current['test_files'])),
    current_only_test_files=sorted(set(current['test_files'])-set(previous['test_files'])),
    hashes={name:digest(ROOT/name) for name in paths},
    scope='Saved evidence and source inspection; no new solver runs or regression suite.')
(HERE/'verification.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(dict(status='passed', timing=[dict(case=c['case'],slowdown_percent=c['slowdown_percent']) for c in cases]),indent=2))
