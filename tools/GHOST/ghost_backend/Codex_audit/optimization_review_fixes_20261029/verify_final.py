"""Verify completed full-suite and paired trial evidence without another solve."""
import hashlib
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TRIAL = HERE/'confirmation'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = read(HERE/'source_hashes.json')
assert all(sha(ROOT/name)==value for name,value in manifest.items())
assert (HERE/'validation_exit_code.txt').read_text().strip()=='0'
test_rows = read(HERE/'validation_results.json')
assert not any(row['outcome']=='failed' for row in test_rows)
assert (ROOT/'geometry/material_columns.py').read_bytes()==(ROOT.parents[1]/'FREDDY/ibc/material_columns.py').read_bytes()
summary = read(TRIAL/'summary.json')
assert [(row['name'], row['arm']) for row in summary['rows']] == [
    ('1_current', 'current'), ('2_baseline', 'baseline'),
    ('3_baseline', 'baseline'), ('4_current', 'current')]
restored = read(TRIAL/'baseline_restored_files.json')
reference = None
verified = []
for row in summary['rows']:
    folder = TRIAL/'runs'/row['name']
    result, monitor = read(folder/'result.json'), read(folder/'monitor.json')
    assert result['status']=='passed' and result['certified']
    assert result['linear_node_count']==14295
    assert monitor['returncode']==0 and monitor['stop_reason'] is None
    for name,digest in result['source_hashes'].items():
        expected = restored[name] if row['arm']=='baseline' and name in restored else sha(ROOT/name)
        assert digest==expected, (row['name'],name)
    with np.load(folder/'fields.npz') as data:
        fields = {key:data[key] for key in data.files}
    assert set(fields) == {'VV', 'HH'}
    if reference is None:
        reference = fields
    equal = {key:bool(np.array_equal(value,reference[key])) for key,value in fields.items()}
    assert all(equal.values())
    if row['arm']=='current':
        assert row['construction_checks']==16122 and row['construction_records']==9
        assert row['construction_live_checks']+row['construction_reused_checks']==16122
    verified.append(dict(name=row['name'], certified=True, bitwise_fields_equal=equal,
                         matching_source_hashes=True, monitor_normal=True))
base = summary['baseline_mean_solve_seconds']
current = summary['current_mean_solve_seconds']
record = dict(full_suite_exit_code=0, full_suite_log=(HERE/'full_suite.log').read_text()[-1500:],
    test_report_rows=len(test_rows), failed_test_rows=0, source_hashes_unchanged=True,
    companion_parser_byte_identical=True, verified_runs=verified, timing_rows=summary['rows'],
    baseline_mean_seconds=base, current_mean_seconds=current,
    overhead_seconds=current-base, overhead_percent=100*(current/base-1),
    observed_mean_below_one_percent=bool(current/base<1.01),
    limitation='Two repetitions per arm on one geometry; this measures the sample mean, not a universal sub-1% bound.',
    pushed=False)
(HERE/'verification.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ('full_suite_exit_code','failed_test_rows','overhead_seconds',
    'overhead_percent','observed_mean_below_one_percent','source_hashes_unchanged')},indent=2))
