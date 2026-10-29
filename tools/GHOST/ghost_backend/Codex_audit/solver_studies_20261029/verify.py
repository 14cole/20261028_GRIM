"""Verify completion, preserve negative evidence, and freeze the review manifest."""
import ast
import hashlib
import json
from pathlib import Path
import re
from study import HERE,ROOT,initial_plan,save


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__=='__main__':
    expected=initial_plan()
    for name in ('comparison_plan.json','validation_plan.json','research_plan.json'):
        expected.extend(read(HERE/name))
    assert len({c['name'] for c in expected})==len(expected)
    statuses={};manifests=[]
    for case in expected:
        directory=HERE/'runs'/case['name']
        result=read(directory/'result.json');monitor=read(directory/'monitor.json')
        assert read(directory/'case.json')==case,case['name']
        status=result['status'];statuses[status]=statuses.get(status,0)+1
        if status=='passed':
            assert monitor['returncode']==0 and monitor['stop_reason'] is None
            if not case.get('task'):
                assert result['quality_passed'] and result['mesh_certified']
                assert (directory/'fields.npz').exists()
            elif case['task']=='accuracy':
                for row in result['results']:
                    assert row['quality'] and row['mesh_certified']
                    for pol in row['polarizations'].values():
                        assert pol['max_rcs_error_db']<result['limits']['rcs_db']
                        if pol['max_complex_relative_error'] is not None:
                            assert pol['max_complex_relative_error']<result['limits']['pec_complex_relative']
            elif case['task']=='lifecycle':
                assert result['completed_sweep_solves']==15 and result['cancel_restart_pairs']==3
                assert all(r['hints_cleared'] and r['run_scope_cleared'] and r['metrics_cleared'] and
                           not r['children'] and not r['solver_threads'] and not r['extra_temp_paths'] and
                           r['worker_reserved']==0 for r in result['records'])
        elif status=='completed':
            assert case['task']=='prototype' and monitor['returncode']==0
            assert len(result['pols'])==2
            for pol in result['pols']:
                assert len(pol['schemes'])==3
                for row in pol['schemes']:
                    if row['passed']:
                        assert row['full_row_backward_error']<=1e-12 and row['normalized_solution_difference']<=1e-8
        else:
            assert status in ('rejected','stopped','process_failed') and result.get('error'),case
        manifests.extend(dict(path=str(p.relative_to(HERE)).replace('\\','/'),sha256=sha(p))
                         for p in directory.iterdir() if p.is_file())
    latest={};runs=[]
    for path in sorted(HERE.glob('validation_results_*.json')):
        rows=read(path);current={}
        for row in rows:
            if current.get(row['test'],{}).get('outcome')!='failed':current[row['test']]=row
        latest.update(current)
        runs.append(dict(file=path.name,passed_reports=sum(r['outcome']=='passed' for r in rows),
                         failed_reports=sum(r['outcome']=='failed' for r in rows)))
    assert latest and all(r['outcome']=='passed' for r in latest.values())
    assert read(HERE/'suite_exit.json')['regression_exit_code']==0
    save(HERE/'validation_summary.json',dict(unique_tests=len(latest),passed=len(latest),unresolved=[],runs=runs,
        semantics='Latest saved result per unique nodeid; passing parents do not mask failed subtests.'))
    # Compare production files against the previously published implementation.
    previous=read(HERE.parent/'followups_20261029/changed_files.json')
    assert all(sha(ROOT/r['path'])==r['after_sha256'] for r in previous)
    for source in HERE.glob('*.py'):ast.parse(source.read_text(encoding='utf-8'),filename=source.name)
    links=[]
    for document in (HERE/'README.md',ROOT/'Claude_audit/CODEX_SOLVER_STUDIES_REVIEW.md'):
        for link in re.findall(r'\]\(([^)]+)\)',document.read_text(encoding='utf-8')):
            if '://' in link:continue
            assert (document.parent/link.split('#')[0]).exists(),link
            links.append(link)
    save(HERE/'evidence_hashes.json',manifests)
    save(HERE/'verification.json',dict(expected_cases=len(expected),completed_cases=sum(statuses.values()),
        statuses=statuses,unique_regression_tests=len(latest),production_files_match_published_snapshot=True,
        report_links_checked=len(links),evidence_files_hashed=len(manifests),audit_python_syntax='passed',
        note='Negative results and time-guard stops are retained and are not successes.'))
    print(json.dumps(read(HERE/'verification.json'),indent=2))
