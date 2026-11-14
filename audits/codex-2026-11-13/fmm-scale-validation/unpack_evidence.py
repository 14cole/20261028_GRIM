"""Verify both immutable evidence archives, restoring original files exactly."""
from pathlib import Path,PurePosixPath
import io,json,hashlib,tarfile,sys
here=Path(__file__).resolve().parent;destination=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else here;total=0
for filename in ['BASELINE_EVIDENCE_MANIFEST.json','EVIDENCE_MANIFEST.json']:
 if not (here/filename).exists():continue
 manifest=json.loads((here/filename).read_text());chunks=[]
 for part in manifest['parts']:
  data=(here/part['name']).read_bytes();assert len(data)==part['bytes'] and hashlib.sha256(data).hexdigest()==part['sha256'];chunks.append(data)
 archive=b''.join(chunks);del chunks
 assert len(archive)==manifest['archive_bytes'] and hashlib.sha256(archive).hexdigest()==manifest['archive_sha256']
 with tarfile.open(fileobj=io.BytesIO(archive),mode='r:xz') as tar:
  index=json.load(tar.extractfile('index.json'));assert index['files']==manifest['files']
  payloads={m.name:tar.extractfile(m).read() for m in tar.getmembers() if m.name.startswith('payload/')}
  for item in index['files']:
   rel=PurePosixPath(item['path']);assert not rel.is_absolute() and '..' not in rel.parts
   target=(destination/rel).resolve();assert target.is_relative_to(destination)
   pieces=[]
   for key in item['chunks']:
    piece=payloads['payload/'+key];assert hashlib.sha256(piece).hexdigest()==key;pieces.append(piece)
   data=b''.join(pieces);assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
   target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);total+=1
print('Verified and restored',total,'files')
