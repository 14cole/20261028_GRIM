"""Deterministic archive, individual SHA-256 manifest, read-back verification."""
import hashlib,json,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent
files=[]
for directory in ('results','geometries','checks','legacy_checks/results','interrupted_run','fallback_verification_repeat'):
    files.extend(f for f in (P/directory).rglob('*') if f.is_file() and '__pycache__' not in f.parts)
files=sorted(set(files));manifest=[]
archive=P/'RAW_EVIDENCE.tar.xz'
with tarfile.open(archive,'w:xz',preset=9) as tar:
    for f in files:
        data=f.read_bytes();name=f.relative_to(P).as_posix();info=tar.gettarinfo(str(f),arcname=name)
        info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0
        with f.open('rb') as handle:tar.addfile(info,handle)
        manifest.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
with tarfile.open(archive,'r:xz') as tar:
    members=tar.getmembers();assert len(members)==len(manifest)
    for m,r in zip(members,manifest):
        data=tar.extractfile(m).read();assert m.name==r['path'] and len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
record=dict(archive=archive.name,bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),members=manifest)
(P/'ARCHIVE_MANIFEST.json').write_text(json.dumps(record,indent=2)+'\n')
print('Verified',len(files),'archive members;',archive.stat().st_size,'bytes')
