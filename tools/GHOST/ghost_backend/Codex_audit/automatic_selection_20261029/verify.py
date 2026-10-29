"""Check terminal evidence, meaningful tests, report links and frozen implementation."""
import ast
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
statuses={};manifest=[]
for case in read(HERE/'plan.json'):
    folder=HERE/'runs'/case['name']
    assert read(folder/'case.json')==case
    result=read(folder/'result.json');monitor=read(folder/'monitor.json')
    status=result['status'];statuses[status]=statuses.get(status,0)+1
    if status in ('passed','diagnostic'):
        assert monitor['returncode']==0 and monitor['stop_reason'] is None
        data=read(folder/'metadata.json')
        assert data['quality_gate']['passed'] and data['mesh_convergence_certified']
        assert (folder/'fields.npz').exists()
        if case.get('diagnose_condition'):
            assert status=='diagnostic' and result['uncertified']
            gates=read(folder/'original_quality_gates.json')
            assert gates and any(not row['gate']['passed'] for row in gates)
        else:assert status=='passed'
        if case.get('switch_after_steps') is not None:
            steps=data['adaptive_mesh']['steps']
            assert len(steps)>case['switch_after_steps']
            assert all(s['backend']==('dense' if i<case['switch_after_steps'] else 'compressed')
                       for i,s in enumerate(steps))
            assert all(s['backend_selection']['audit_transition']['selected']==s['backend'] for s in steps)
    else:
        assert status in ('stopped','rejected') and result.get('error')
    for path in folder.iterdir():
        if path.is_file():manifest.append(dict(path=str(path.relative_to(HERE)).replace('\\','/'),sha256=sha(path)))
assert read(HERE/'suite_exit.json')['exit_code']==0
assert (HERE/'validation_exit_code.txt').read_text().strip()=='0'
latest={};runs=[]
for path in sorted(HERE.glob('validation_results_*.json')):
    results=read(path);current={}
    for row in results:
        if current.get(row['test'],{}).get('outcome')!='failed':current[row['test']]=row
    latest.update(current)
    runs.append(dict(file=path.name,passed_reports=sum(r['outcome']=='passed' for r in results),
                     failed_reports=sum(r['outcome']=='failed' for r in results)))
assert latest and all(r['outcome']=='passed' for r in latest.values())
for row in read(HERE/'changed_files.json'):assert sha(ROOT/row['path'])==row['after_sha256']
for path in HERE.glob('*.py'):ast.parse(path.read_text(encoding='utf-8'))
links=[]
for document in (HERE/'README.md',ROOT/'Claude_audit/CODEX_AUTOMATIC_SELECTION_REVIEW.md'):
    for target in re.findall(r'\]\(([^)]+)\)',document.read_text(encoding='utf-8')):
        if '://' in target:continue
        assert (document.parent/target.split('#')[0]).exists(),target
        links.append(target)
summary=dict(planned_cases=len(read(HERE/'plan.json')),terminal_statuses=statuses,
    unique_passing_tests=len(latest),test_runs=runs,implementation_hashes_match=True,
    report_links_checked=len(links),evidence_files_hashed=len(manifest),audit_syntax='passed',
    note='Diagnostic runs do not establish certified capacity; rejected and stopped cases remain visible.')
(HERE/'evidence_hashes.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(HERE/'verification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
