"""Verify archive parts and restore hash-checked complete evidence files."""
from pathlib import Path,PurePosixPath
import json,hashlib,tarfile,io,sys
here=Path(__file__).resolve().parent
manifest=json.loads((here/'EVIDENCE_MANIFEST.json').read_text())
chunks=[]
for part in manifest['parts']:
 data=(here/part['name']).read_bytes()
 if len(data)!=part['bytes'] or hashlib.sha256(data).hexdigest()!=part['sha256']:raise ValueError('Bad archive part: '+part['name'])
 chunks.append(data)
archive=b''.join(chunks);del chunks
if len(archive)!=manifest['archive_bytes'] or hashlib.sha256(archive).hexdigest()!=manifest['archive_sha256']:raise ValueError('Bad complete archive')
destination=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else here
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:xz') as tar:
 index=json.load(tar.extractfile('index.json'))
 payloads={member.name:tar.extractfile(member).read() for member in tar.getmembers() if member.name.startswith('payload/')}
 if index['files']!=manifest['files']:raise ValueError('Archive index differs from manifest')
 for item in index['files']:
  rel=PurePosixPath(item['path'])
  if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe evidence path')
  target=(destination/rel).resolve()
  if not target.is_relative_to(destination):raise ValueError('Evidence path escapes destination')
  pieces=[]
  for key in item['chunks']:
   piece=payloads['payload/'+key]
   if hashlib.sha256(piece).hexdigest()!=key:raise ValueError('Bad evidence chunk')
   pieces.append(piece)
  data=b''.join(pieces)
  if len(data)!=item['bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Bad evidence file: '+item['path'])
  target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
print(f"Verified and restored {len(index['files'])} evidence files to {destination}")
