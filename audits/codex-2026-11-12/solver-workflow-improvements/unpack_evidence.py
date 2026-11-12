"""Verify every archive part and member before extracting to a new directory."""
import hashlib,io,json,pathlib,sys,tarfile
root=pathlib.Path(__file__).resolve().parent
manifest=json.loads((root/'EVIDENCE_MANIFEST.json').read_text())
def digest(data):return hashlib.sha256(data).hexdigest()
parts=[]
for row in manifest['parts']:
 data=(root/row['path']).read_bytes()
 if len(data)!=row['bytes'] or digest(data)!=row['sha256']:raise ValueError('Invalid archive part: '+row['path'])
 parts.append(data)
data=b''.join(parts)
if digest(data)!=manifest['archive_sha256']:raise ValueError('Invalid complete archive')
target=pathlib.Path(sys.argv[1])
if target.exists():raise FileExistsError('Choose a new output directory: '+str(target))
verified={}
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
 for member in archive:
  path=pathlib.PurePosixPath(member.name)
  if not member.isfile() or path.is_absolute() or '..' in path.parts or member.name in verified:raise ValueError('Unsafe or duplicate archive member')
  expected=manifest['members'].get(member.name)
  content=archive.extractfile(member).read()
  if expected is None or len(content)!=expected['bytes'] or digest(content)!=expected['sha256']:raise ValueError('Invalid member: '+member.name)
  verified[member.name]=content
if set(verified)!=set(manifest['members']):raise ValueError('Missing archive members')
target.mkdir(parents=True)
for name,content in verified.items():
 dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
print(f'Verified and extracted {len(verified)} files to {target}')
