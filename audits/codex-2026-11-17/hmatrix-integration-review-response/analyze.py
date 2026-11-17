"""Verify pinned reviewer records and fresh bounded followups; no solves here."""
import hashlib, json
from pathlib import Path
import numpy as np

R = Path(__file__).resolve().parent
C = R/'claude'
read = lambda p: json.loads(p.read_text())
hash_bytes = lambda b: hashlib.sha256(b).hexdigest()
provenance = read(R/'source-provenance.json')
for f in provenance['files']:
    b = (C/f['path']).read_bytes()
    assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest() == f['sha']
hashes = read(C/'array_hashes.json')
record = lambda label: read(C/'results'/(label+'.json'))
def field(rec):
    return np.array([complex(x['rcs_amp_real'], x['rcs_amp_imag']) for x in rec['samples']])

cases = ['multilayer-TM','partial-TE','partial-TM','pec-circle-TE','pec-cavity-TM','coated-TE']
pairs = {}
for case in cases:
    old, new = 'old-'+case+'-compressed', 'new-'+case+'-compressed'
    a, b = record(old), record(new)
    assert not a['error'] and not b['error']
    assert field(a).tobytes() == field(b).tobytes()
    assert hashes[old+'-solve0000.npz'] == hashes[new+'-solve0000.npz']
    assert a['metadata']['condition_est_max'] == b['metadata']['condition_est_max']
    assert a['metadata']['condition_est_computed'] and b['metadata']['condition_est_computed']
    assert a['metadata']['quality_gate']['passed'] and b['metadata']['quality_gate']['passed']
    calls = lambda d: [{k:x[k] for k in ('phase','trans','columns','corrections','tolerance')} for x in d['hooks']['inverse_calls']]
    assert calls(a) == calls(b)
    acct = b['hooks']['accounting']
    assert acct['high_water_bytes'] == acct['high_water_with_check_bytes'] == acct['final_bytes'][-1]
    assert a['hooks']['accounting']['final_bytes'] == acct['final_bytes']
    peak_delta = 100*(b['peak_gib']/a['peak_gib']-1)
    assert abs(peak_delta) < 2
    pairs[case] = dict(field_bytes_equal=True,published_density_rhs_hashes_equal=True,
        condition_equal=True,corrections_equal=True,peak_change_percent=peak_delta,
        final_inverse_bytes=acct['final_bytes'][-1],formulation=b['metadata']['formulation'])

dense = {}
for case in cases[3:]:
    x, y = field(record('new-'+case+'-compressed')), field(record('dense-'+case))
    error = float(np.max(abs(x-y))/max(np.max(abs(y)),1e-300))
    assert error < 1e-8
    dense[case] = dict(field_peak_normalized_error=error,angles=len(x))

caps = {}
for label in ('old-multilayer-TM-cap690','new-multilayer-TM-cap690','old-multilayer-TM-cap650','new-multilayer-TM-cap650'):
    d = record(label)
    caps[label] = dict(builds=d['hooks']['builds'],rejected=bool(d['error']),
                      final_inverse_bytes=d['hooks']['accounting']['final_bytes'][-1])
assert caps['old-multilayer-TM-cap650']['rejected']
assert not caps['new-multilayer-TM-cap650']['rejected']
assert caps['new-multilayer-TM-cap690']['builds'] == 1
assert caps['old-multilayer-TM-cap690']['builds'] == 2
assert hashes['new-multilayer-TM-cap690-solve0000.npz'] == hashes['new-multilayer-TM-compressed-solve0000.npz']
assert hashes['new-multilayer-TM-cap650-solve0000.npz'] == hashes['old-multilayer-TM-cap690-solve0000.npz']

audit_count = 0
for case in ('multilayer-TM','partial-TE','pec-circle-TE'):
    for a in record('new-'+case+'-audit')['hooks']['audit']:
        assert a['shortfalls'] == 0
        audit_count += a['entries']
assert audit_count == 3891
diagonal = read(C/'claude_diagonal_queries_production.json')
assert sum(x['queries'] for x in diagonal.values()) == 70
assert not any(x['any_exceeds_4q_plus_1'] for x in diagonal.values())

cancellations, active = 0, 0
for p in sorted((C/'out').glob('cancel-*.log')):
    records = [json.loads(line) for line in p.read_text().splitlines() if line.startswith('{')]
    fired = [json.loads(line.strip()[6:]) for line in p.read_text().splitlines() if line.strip().startswith('fired ')]
    assert len(records) == len(fired) == 6
    for r, f in zip(records, fired):
        assert r['raised'] == 'Cancel' and r['recovered'] and r['bitwise_equal_control']
        assert not r['workers_alive_after'] and r['inverse_objects_alive_after_gc'] == r['active_tasks_after'] == 0
        assert r['tasks_started_total'] == r['tasks_finished_total']
        assert r['pending_construction_bytes'] == [None, None]
        cancellations += 1
        active += int(f['active_product_tasks'] > 0)
assert cancellations == 24 and active >= 3
control = hashes['star8192-t1-control.npz']
for t in (2, 4):
    for key in ('density','rhs','angles'):
        assert control[key] == hashes[f'star8192-t{t}-control.npz'][key]

process_count = 0
for p in (C/'results').glob('*.time.json'):
    expected = 2 if p.name == 'old-multilayer-TM-cap650.time.json' else 0
    assert read(p)['returncode'] == expected
    process_count += 1
assert process_count == 23
local = read(R/'prior-32k-fingerprints.json')
star_hashes = hashes['new-star32768-cap2900-batch0000.npz']
for key in ('angles','density','rhs','field'):
    assert local[key] == star_hashes[key]['sha256_c_order']
star = record('new-star32768-cap2900')
assert star['event']['gmres_columns'] == 0 and star['event']['refinement_steps'] == 3
assert max(x['max_exact_row_backward_error'] for x in star['batches']) < 1e-12

gather = read(R/'fresh/claude_production_gather_test.json')
assert gather['cases'] == 20700 and gather['mismatches'] == 0
copy = read(R/'fresh/claude_copy_path_test.json')
assert len(copy) == 9
for x in copy[:-1]:
    assert x['error'] is None and x['reserved_equals_result_bytes']
    assert x['in_place_allowance_ok'] and x['copy_step_live_or_additional_covers_copy'] and x['second_step_counts_copy_as_live']
    if x['name'] != 'zero rank': assert x['rel_error'] < 1e-12
assert copy[-1]['error'] == 'MemoryError' and copy[-1]['reserved_before'] == copy[-1]['reserved_after']

headroom = []
for variant in ('baseline','candidate'):
    entries = read(R/'fresh'/('headroom-'+variant+'.json'))
    assert len(entries) == 6
    for x in entries:
        assert x['pending_after'] == x['registered_after'] == x['construction_bytes_after'] == 0
        if x['probe']:
            assert x['status'] == ('query_reached' if variant == 'baseline' else 'memory_rejected')
            assert x['query_calls'] == (1 if variant == 'baseline' else 0)
        else:
            assert x['status'] == 'built' and max(x['solve_max_abs_errors']) < 1e-14
        headroom.append({k:x[k] for k in ('variant','side','probe','reservation_bytes','status','query_calls')})

out = dict(all_pass=True,pinned_files=len(provenance['files']),old_new_pairs=pairs,
    replayed_dense_field_comparisons=dense,cap_outcomes=caps,reviewer_audit_entries=audit_count,
    reviewer_cancellations=cancellations,reviewer_active_task_cancellations=active,
    reviewer_process_records=process_count,prior_independent_32k_array_hashes_match=True,
    fresh_selector_cases=gather['cases'],fresh_copy_cases=len(copy),fresh_controlled_headroom_cases=headroom,
    new_physical_solves=0,scope='Reviewer JSON/log replay and prior independent array fingerprints; fresh unit/admission tests. No new large solve or physical-pressure benchmark.')
(R/'analysis.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
