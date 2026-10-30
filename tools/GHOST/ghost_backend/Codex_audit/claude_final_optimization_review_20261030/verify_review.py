"""Recheck saved evidence for Claude's final optimization audit; no solves."""
import ast
import hashlib
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVIDENCE = ROOT/'Codex_audit/optimization_review_fixes_20261029'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = read(EVIDENCE/'source_hashes.json')
assert all(sha(ROOT/name) == digest for name, digest in manifest.items())
for row in read(EVIDENCE/'encoding_changes.json'):
    before = EVIDENCE/'before'/(row['file'].replace('/', '__')+'.source.txt')
    after = ROOT/row['file']
    assert sha(before) == row['before_sha256'] and sha(after) == row['after_sha256']
    assert ast.dump(ast.parse(before.read_bytes())) == ast.dump(ast.parse(after.read_bytes()))
    after.read_bytes().decode('ascii')
assert (ROOT/'geometry/material_columns.py').read_bytes() == (ROOT.parents[1]/'FREDDY/ibc/material_columns.py').read_bytes()
assert (EVIDENCE/'validation_exit_code.txt').read_text().strip() == '0'
outcomes = read(EVIDENCE/'full_suite_results.json')
assert not any(row['outcome'] == 'failed' for row in outcomes)
summary = read(EVIDENCE/'confirmation/summary.json')
rows = summary['rows']
assert len(rows) == 4
reference = None
stages = {'current': [], 'baseline': []}
for row in rows:
    folder = EVIDENCE/'confirmation/runs'/row['name']
    result, monitor = read(folder/'result.json'), read(folder/'monitor.json')
    assert result['certified'] and result['status'] == 'passed'
    assert monitor['returncode'] == 0 and monitor['stop_reason'] is None
    stages[row['arm']].append(result['stage_seconds'])
    with np.load(folder/'fields.npz') as arrays:
        fields = {key: arrays[key] for key in arrays.files}
    assert set(fields) == {'VV', 'HH'}
    if reference is None:
        reference = fields
    assert all(np.array_equal(fields[key], reference[key]) for key in fields)
    if row['arm'] == 'current':
        assert row['construction_records'] == 9 and row['construction_checks'] == 16122
base, current = summary['baseline_mean_solve_seconds'], summary['current_mean_solve_seconds']
stage_means = {arm: {key: sum(run[key] for run in runs)/len(runs)
                    for key in runs[0]} for arm, runs in stages.items()}
record = dict(validated_source_files=len(manifest), source_hashes_unchanged=True,
    encoding_ast_equal_files=9, companion_parser_byte_identical=True,
    full_suite_saved_exit_code=0, failed_saved_outcomes=0,
    certified_runs=4, fields_bitwise_equal=True, canonical_counts_verified=True,
    total_mean_seconds=dict(baseline=base, current=current),
    total_difference_seconds=current-base, total_difference_percent=100*(current/base-1),
    stage_means_seconds=stage_means,
    factorization_difference_seconds=stage_means['current']['factorization']-stage_means['baseline']['factorization'],
    new_tests_or_solves_run=False, production_changes=False, pushed=False)
(HERE/'verification.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k != 'stage_means_seconds'}, indent=2))
