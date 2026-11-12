"""Record exact production changes and native binary identity against baseline."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent;old=Path(sys.argv[1]);new=Path(sys.argv[2])
changes=[];natives=[];digest=hashlib.sha256()
for file in sorted((new/'tools/GHOST').rglob('*')):
    if not file.is_file() or '__pycache__' in file.parts or file.suffix=='.pyc':continue
    rel=file.relative_to(new);before=old/rel;b=file.read_bytes()
    if not before.exists() or before.read_bytes()!=b:changes.append(str(rel))
    if 'ghost_backend' in rel.parts and file.suffix=='.py':digest.update(rel.as_posix().encode()+b'\0'+b+b'\0')
    if file.suffix in ('.dll','.so'):
        assert before.exists() and before.read_bytes()==b
        natives.append(dict(path=str(rel),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b)))
for file in (old/'tools/GHOST').rglob('*'):
    if file.is_file() and '__pycache__' not in file.parts and file.suffix!='.pyc':assert (new/file.relative_to(old)).exists()
early=hashlib.sha256()
for file in sorted((new/'tools/GHOST/ghost_backend').rglob('*.py')):
    content=file.read_bytes()
    if file.name=='options.py':content=content.replace(b'                attempt_start=time.perf_counter()\r\n',b'')
    early.update(file.relative_to(new).as_posix().encode()+b'\0'+content+b'\0')
assert early.hexdigest()=='dc37e91c015799885dd0d1529ffbe5770147ee3381b100726ba34659ab7ffbe2'
value=dict(source_sha256=digest.hexdigest(),changed_files=changes,native_binaries_unchanged=natives,early_explicit_runs_sha256=early.hexdigest(),early_difference='Only the Automatic retry attempt_start timer assignment was absent; explicit numerical paths identical.')
(P/'SOURCE_IDENTITY.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value,indent=2))
