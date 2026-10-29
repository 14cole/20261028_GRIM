"""Capture the reviewed implementation without depending on a Git checkout."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
baseline = json.loads((HERE / 'baseline_hashes.json').read_text())
paths = [*baseline, 'tests/test_factorization_audit_resources.py']
records, patch = [], []
for name in paths:
    source, before, after = ROOT / name, HERE / 'before' / name, HERE / 'after' / name
    after.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, after)
    old = before.read_text(encoding='utf-8').splitlines(keepends=True) if before.exists() else []
    new = source.read_text(encoding='utf-8').splitlines(keepends=True)
    patch.extend(difflib.unified_diff(old, new, fromfile='a/' + name if old else '/dev/null', tofile='b/' + name))
    records.append(dict(path=name, before_sha256=baseline.get(name),
                        after_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
(HERE / 'implementation.patch').write_text(''.join(patch), encoding='utf-8')
(HERE / 'changed_files.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
print('Captured', len(records), 'implementation files, plus their unified diff.')
