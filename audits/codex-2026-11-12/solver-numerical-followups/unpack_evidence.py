"""Verify archive/member hashes and extract into a new directory (Python 3.12+)."""
import hashlib,json,pathlib,sys,tarfile,io
root=pathlib.Path(__file__).parent
manifest=json.loads((root/'EVIDENCE_MANIFEST.json').read_text())
parts=[]
for entry in manifest['parts']:
 data=(root/entry['path']).read_bytes()
 assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256'],entry['path']
 parts.append(data)
data=b''.join(parts)
assert hashlib.sha256(data).hexdigest()==manifest['archive_sha256']
target=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'evidence')
target.mkdir(exist_ok=False,parents=True)
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
 assert sorted(archive.getnames())==sorted(manifest['members'])
 archive.extractall(target,filter='data')
for name,entry in manifest['members'].items():
 data=(target/name).read_bytes()
 assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256'],name
print('Verified and extracted',len(manifest['members']),'files into',target)
