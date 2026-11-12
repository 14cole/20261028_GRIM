"""Verify split archive and safely extract complete raw evidence.

Usage: python unpack_evidence.py [OUTPUT_DIRECTORY]
Default: a new raw-evidence/ directory beside this script.
"""
import hashlib,io,json,sys,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent;destination=Path(sys.argv[1]) if len(sys.argv)>1 else P/'raw-evidence'
manifest=json.loads((P/'ARCHIVE_MANIFEST.json').read_text());chunks=[]
for row in manifest['parts']:
 b=(P/row['path']).read_bytes();assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256'],row['path'];chunks.append(b)
archive=b''.join(chunks);assert hashlib.sha256(archive).hexdigest()==manifest['archive_sha256']
if destination.exists() and any(destination.iterdir()):raise SystemExit('Choose an empty extraction directory; existing results are not overwritten.')
destination.mkdir(parents=True,exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
 members=tar.getmembers();assert {m.name for m in members}=={r['path'] for r in manifest['files']}
 for member in members:
  path=Path(member.name)
  assert member.isfile() and not path.is_absolute() and '..' not in path.parts,member.name
 tar.extractall(destination,filter='data')
for row in manifest['files']:
 b=(destination/row['path']).read_bytes();assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256'],row['path']
print('Verified and extracted',len(manifest['files']),'raw evidence files to',destination)
