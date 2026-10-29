"""Freeze the production/test diff for Claude without staging or committing."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
REPO=ROOT.parents[2]
BASE='30ce6fb'
paths=['execution/policy.py','execution/selection.py','execution/timing_history.py',
       'twod/adaptivity.py','tests/test_selection_explanations.py']
rows=[];patch=[]
for name in paths:
    relative='tools/GHOST/ghost_backend/'+name
    old=subprocess.run(['git','show',BASE+':'+relative],cwd=REPO,capture_output=True)
    before=old.stdout if old.returncode==0 else b''
    after=(ROOT/name).read_bytes()
    rows.append(dict(path=name,before_sha256=hashlib.sha256(before).hexdigest() if old.returncode==0 else None,
                     after_sha256=hashlib.sha256(after).hexdigest(),new_file=old.returncode!=0))
    patch.extend(difflib.unified_diff(before.decode('utf-8').splitlines(keepends=True),
        after.decode('utf-8').splitlines(keepends=True),fromfile='a/'+relative,tofile='b/'+relative))
(HERE/'changed_files.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
(HERE/'implementation.patch').write_text(''.join(patch),encoding='utf-8',newline='\n')
print('Captured',len(rows),'implementation/test files against',BASE)
