"""Restore hash-verified array files without trusting tar extraction paths."""
import hashlib,io,json,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
m=json.loads((HERE/'EVIDENCE_MANIFEST.json').read_text())
chunks=[]
for item in m['parts']:
    data=(HERE/item['name']).read_bytes()
    assert hashlib.sha256(data).hexdigest()==item['sha256']
    chunks.append(data)
data=b''.join(chunks)
assert hashlib.sha256(data).hexdigest()==m['archive_sha256']
expected={x['name']:x for x in m['files']}
with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as archive:
    assert len(archive.getmembers())==len(expected)
    for member in archive.getmembers():
        assert member.isfile() and member.name in expected
        path=HERE/member.name
        assert path.resolve().is_relative_to(HERE.resolve())
        content=archive.extractfile(member).read()
        assert hashlib.sha256(content).hexdigest()==expected[member.name]['sha256']
        if path.exists():assert path.read_bytes()==content
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(content)
print('Verified and restored',len(expected),'array archives.')
