"""Package only synthetic stress evidence; verify every archive member before publication."""
import hashlib,json,sys,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent
archive=P/'RAW_EVIDENCE.tar.xz'
members=[]
files=[f for folder in ('results','geometries') for f in sorted((P/folder).iterdir()) if f.is_file()]
for f in files:
    data=f.read_bytes();members.append(dict(path=f.relative_to(P).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
if '--reuse' not in sys.argv:
    with tarfile.open(archive,'w:xz',preset=9) as z:
        for f in files:
            info=z.gettarinfo(str(f),arcname=f.relative_to(P).as_posix());info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0
            with f.open('rb') as src:z.addfile(info,src)
expected={m['path']:m for m in members};seen=set()
with tarfile.open(archive,'r|xz') as z:
    for info in z:
        assert info.isfile() and info.name in expected
        r=expected[info.name];data=z.extractfile(info).read()
        assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
        assert info.name not in seen;seen.add(info.name)
assert seen==set(expected)
manifest=dict(archive=archive.name,bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),members=members)
(P/'ARCHIVE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
assets=[f for f in P.iterdir() if f.is_file() and f.suffix in ('.py','.json','.md','.csv','.xz') and f.name!='PUBLICATION_ASSETS.json']
assets+=list((P/'figures').glob('*.svg'))+list((P/'figures').glob('*.png'))
records=[]
for f in sorted(assets):
    data=f.read_bytes()
    records.append(dict(path=f.relative_to(P).as_posix(),bytes=len(data),git_sha=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),sha256=hashlib.sha256(data).hexdigest()))
(P/'PUBLICATION_ASSETS.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(dict(archive_bytes=manifest['bytes'],archive_members=len(members),assets=len(records),total_bytes=sum(r['bytes'] for r in records)),indent=2))
