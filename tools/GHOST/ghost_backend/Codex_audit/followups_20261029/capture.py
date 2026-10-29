"""Freeze follow-up source changes and verify their saved audit evidence."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2), encoding='utf-8')


def capture():
    originals = {p.relative_to(HERE / 'before').as_posix(): p
                 for p in (HERE / 'before').rglob('*.py')}
    baseline = {name: digest(path) for name, path in originals.items()}
    if (HERE / 'baseline_hashes.json').exists():
        assert read(HERE / 'baseline_hashes.json') == baseline, 'Baseline changed'
    save('baseline_hashes.json', baseline)
    names = sorted(set(originals) | {'compressed/preconditioner_hints.py',
                                    'tests/test_large_geometry_followups.py'})
    manifest, patch = [], []
    for name in names:
        source = ROOT / name
        after = source.read_text(encoding='utf-8')
        ast.parse(after, filename=name)
        old = originals.get(name)
        before = old.read_text(encoding='utf-8') if old else ''
        if before == after:
            continue
        target = HERE / 'after' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest.append(dict(path=name, before_sha256=digest(old) if old else None,
                             after_sha256=digest(source), status='modified' if old else 'added'))
        patch.extend(difflib.unified_diff(before.splitlines(keepends=True),
            after.splitlines(keepends=True), fromfile='a/' + name if old else '/dev/null',
            tofile='b/' + name))
    save('changed_files.json', manifest)
    (HERE / 'implementation.patch').write_text(''.join(patch), encoding='utf-8')

    latest, runs = {}, []
    for path in sorted(HERE.glob('validation_results_*.json')):
        rows = read(path)
        runs.append(dict(file=path.name, passed_reports=sum(r['outcome'] == 'passed' for r in rows),
                         failed_reports=sum(r['outcome'] == 'failed' for r in rows)))
        per_run = {}
        for row in rows:
            # Passing parent reports must not mask failed unittest subtests.
            if per_run.get(row['test'], {}).get('outcome') != 'failed':
                per_run[row['test']] = row
        latest.update(per_run)
    summary = dict(unique_tests=len(latest), passed=sum(r['outcome'] == 'passed' for r in latest.values()),
        unresolved=[r for r in latest.values() if r['outcome'] != 'passed'], runs=runs,
        semantics='Latest saved result for each unique test; subtests not counted separately.')
    save('validation_summary.json', summary)
    assert latest and not summary['unresolved'], summary['unresolved']

    links = []
    for document in (HERE / 'README.md', ROOT / 'Claude_audit/CODEX_FOLLOWUP_IMPLEMENTATION_REVIEW.md'):
        for reference in re.findall(r'\]\(([^)]+)\)', document.read_text(encoding='utf-8')):
            if '://' in reference:
                continue
            target = (document.parent / reference.split('#')[0]).resolve()
            assert target.exists(), str(target)
            links.append(str(target.relative_to(ROOT)))
    measurements = read(HERE / 'measurements.json')
    assert len(measurements['runs']) == 5
    for name, result in measurements['runs'].items():
        assert result['status'] == 'ok' and result['quality_passed'] and result['mesh_certified'], name
        assert read(HERE / 'benchmarks' / name / 'result.json')['angle_count'] == 361
    for field in ('hint_fields', 'leaf_fields'):
        assert all(v['angles'] == 361 for v in measurements[field].values())
    loss = read(HERE / 'loss_study_refined.json')
    assert len(loss) == 6 and all(r['status'] == 'passed' and
        r['full_streamed_backward_error'] < 1e-12 for r in loss)
    reciprocal = read(HERE / 'reciprocal_query_study.json')['runs']
    assert len(reciprocal) == 2 and all(r['cache_hits'] == 0 and
        r['reciprocal_hits'] == 0 and r['relative_solution_difference'] < 1e-12 for r in reciprocal)
    save('verification.json', dict(source_hashes_verified=len(manifest), python_syntax='passed',
        report_links_checked=len(links), report_links_valid=True, certified_trials_passed=5,
        refined_loss_experiments_passed=6, reciprocal_experiment_verified=True,
        source_matches_snapshot=all(digest(ROOT / r['path']) == r['after_sha256'] ==
            digest(HERE / 'after' / r['path']) for r in manifest)))
    print(json.dumps(dict(changed_files=len(manifest), unique_tests=summary['unique_tests'],
                         passed=summary['passed'], certified_trials=5)))


if __name__ == '__main__':
    capture()
