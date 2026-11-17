"""Check evidence completeness and the exact production scope before publication."""
import ast, hashlib, json, os, platform, subprocess, sys
from pathlib import Path
import numpy as np
import scipy
from threadpoolctl import threadpool_info

root = Path(__file__).resolve().parent
base = Path(os.environ['BASE_GRIM_ROOT'])
candidate = Path(os.environ['GRIM_ROOT'])
inventory = json.loads((root/'baseline-source-inventory.json').read_text())
expected = json.loads((root/'production-verification.json').read_text())['changes']
expected_paths = {x['path'] for x in expected}
blob = lambda data: hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
changes = []
for item in inventory:
    path = item['path']
    old = (base/path).read_bytes()
    assert blob(old) == item['sha'], path
    new = (candidate/path).read_bytes()
    if old != new:
        changes.append(path)
        assert path in expected_paths, path
for item in expected:
    path = item['path']
    data = (candidate/path).read_bytes()
    assert hashlib.sha256(data).hexdigest() == item['new_sha256'], path
    ast.parse(data, filename=path)
    if item['new_file']:
        assert not (base/path).exists()
        changes.append(path)
assert set(changes) == expected_paths
candidate_paths = {str(p.relative_to(candidate)) for p in (candidate/'tools/GHOST').rglob('*')
                   if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
assert candidate_paths == {x['path'] for x in inventory} | expected_paths
parsed = []
for path in sorted(root.glob('*.py')):
    ast.parse(path.read_bytes(), filename=path.name)
    parsed.append(path.name)
subprocess.run(['git','apply','--check',str(root/'production-change.patch')],cwd=base,check=True)
analysis = json.loads((root/'analysis.json').read_text())
replay = json.loads((root/'replayed-analysis.json').read_text())
assert analysis == replay and analysis['all_pass']
assert json.loads((root/'evidence-verification.json').read_text())['all_bits_and_layouts_match']
assert json.loads((root/'claude_gather_v2_tests.json').read_text())['v2_mismatches'] == 0
assert 'Ran 9 tests' in (root/'build-tests.log').read_text() and '\nOK\n' in (root/'build-tests.log').read_text()
environment = dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform(),
    memory_limit=Path('/sys/fs/cgroup/memory.max').read_text().strip(),cpu_quota=Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
    blas=threadpool_info(),baseline_commit='5fec63200d48d6dd7536221d992b3e1836a1647c',
    publication_parent='c536f7e7ab5dc12692e02c0035d3ad653299905f',performance_threads=dict(assembly=1,blas=1))
(root/'environment.json').write_text(json.dumps(environment,indent=2))
result=dict(all_pass=True,baseline_files_verified=len(inventory),production_changes=sorted(changes),
    audit_scripts_parsed=parsed,patch_applies_to_baseline=True,archive_replay_equals_original_analysis=True,
    completed_field_solves=analysis['completed_field_solves'],all_original_native_libraries_unchanged=True,
    inherited_inverse_upgrade_fix_unchanged=True)
(root/'final-verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
