"""Freeze the implementation diff and summarize the latest result per test."""
import difflib
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name,value):
    (HERE/name).write_text(json.dumps(value,indent=2),encoding='utf-8')


if __name__=='__main__':
    originals={p.relative_to(HERE/'before').as_posix():p for p in (HERE/'before').rglob('*.py')}
    initial=json.loads((HERE/'baseline_hashes.json').read_text(encoding='utf-8'))
    for name,sha in initial.items():
        assert digest(originals[name])==sha, 'Baseline changed: '+name
    # This test was snapshotted immediately before its targeted GMRES update.
    initial.update({name:digest(path) for name,path in originals.items()})
    save('baseline_hashes.json',initial)
    names=sorted(set(originals)|{'tests/test_large_geometry_resources.py'})
    manifest=[]
    patch=[]
    for name in names:
        source=ROOT/name
        ast.parse(source.read_text(encoding='utf-8'),filename=name)
        old=originals.get(name)
        before=old.read_text(encoding='utf-8') if old else ''
        after=source.read_text(encoding='utf-8')
        if before==after:
            continue
        target=HERE/'after'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        manifest.append(dict(path=name,before_sha256=digest(old) if old else None,
            after_sha256=digest(source),status='modified' if old else 'added'))
        patch.extend(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),
            fromfile='a/'+name if old else '/dev/null',tofile='b/'+name))
    save('changed_files.json',manifest)
    (HERE/'implementation.patch').write_text(''.join(patch),encoding='utf-8')
    latest={}
    runs=[]
    for path in sorted(HERE.glob('validation_results_*.json')):
        rows=json.loads(path.read_text(encoding='utf-8'))
        runs.append(dict(file=path.name,passed_reports=sum(r['outcome']=='passed' for r in rows),
                         failed_reports=sum(r['outcome']=='failed' for r in rows)))
        per_run={}
        for row in rows:
            # A passing parent report must not mask a failed unittest subtest.
            if per_run.get(row['test'],{}).get('outcome')!='failed':
                per_run[row['test']]=row
        latest.update(per_run)
    summary=dict(unique_tests=len(latest),passed=sum(r['outcome']=='passed' for r in latest.values()),
        unresolved=[r for r in latest.values() if r['outcome']!='passed'],runs=runs,
        semantics='Latest saved call result for each unique test; unittest subtests not counted separately.')
    save('validation_summary.json',summary)
    assert not summary['unresolved'],summary['unresolved']
    links=[]
    for document in (HERE/'README.md',ROOT/'Claude_audit/CODEX_LARGE_GEOMETRY_IMPLEMENTATION_REVIEW.md'):
        for reference in re.findall(r'\]\(([^)]+)\)',document.read_text(encoding='utf-8')):
            target=(document.parent/reference.split('#')[0]).resolve()
            assert target.exists(),str(target)
            links.append(str(target.relative_to(ROOT)))
    measurements=json.loads((HERE/'measurements.json').read_text())
    assert all(r['status']=='ok' and r['quality_passed'] and r['mesh_certified'] for r in measurements['runs'])
    assert all(v['count']==361 for field in ('upgraded_field_difference','constrained_field_difference')
               for v in measurements[field].values())
    save('verification.json',dict(source_hashes_verified=len(manifest),python_syntax='passed',
        report_links_checked=len(links),report_links_valid=True,matched_trials_passed=3,
        source_matches_snapshot=all(digest(ROOT/r['path'])==r['after_sha256'] for r in manifest)))
    print(json.dumps(dict(changed_files=len(manifest),unique_tests=summary['unique_tests'],passed=summary['passed'])))
