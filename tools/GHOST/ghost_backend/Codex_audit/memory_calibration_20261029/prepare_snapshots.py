"""Export immutable source revisions for comparison, without changing the checkout."""
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPO = ROOT.parents[2]
PREFIX = 'tools/GHOST/ghost_backend/'
manifest = {}
for revision in ('63429ba', 'b233c19'):
    target = HERE/'scratch'/revision
    target.mkdir(parents=True, exist_ok=False)
    paths = subprocess.check_output(['git','ls-tree','--name-only',revision,PREFIX],cwd=REPO,text=True).splitlines()
    paths = [p for p in paths if p.rsplit('/',1)[-1] not in ('Codex_audit','Claude_audit','trials','tests')]
    archive = target/'source.zip'
    subprocess.run(['git','archive','--format=zip','--output='+str(archive),revision,*paths],cwd=REPO,check=True)
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            path = (target/item.filename).resolve()
            if not path.is_relative_to(target.resolve()): raise ValueError(item.filename)
        source.extractall(target)
    backend = target/PREFIX
    files = {str(p.relative_to(backend)):hashlib.sha256(p.read_bytes()).hexdigest()
             for p in backend.rglob('*') if p.is_file()}
    manifest[revision] = dict(commit=subprocess.check_output(['git','rev-parse',revision],cwd=REPO,text=True).strip(),
        backend=str(backend), files=files)
    # Git does not track these local native builds. Both revisions must use
    # exactly the same binaries; otherwise fallback Python timings are invalid.
    native = {}
    for name in ('ghost_far.dll', 'ghost_near.dll', 'ghost_table.dll'):
        relative = Path('twod/assembly/native')/name
        original = ROOT/relative
        if not original.is_file():raise RuntimeError('Build native kernels before benchmarking: '+str(original))
        (backend/relative).parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(original,backend/relative)
        native[str(relative)] = hashlib.sha256(original.read_bytes()).hexdigest()
    manifest[revision]['native_artifacts'] = native
(HERE/'snapshot_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print({key:len(value['files']) for key,value in manifest.items()})
