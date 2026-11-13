"""Verify, reassemble and extract the evidence into a NEW output directory."""
import hashlib,json,pathlib,sys,tarfile,tempfile,shutil
base=pathlib.Path(__file__).resolve().parent
manifest=json.loads((base/'EVIDENCE_MANIFEST.json').read_text())
out=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'fmm-followup-evidence').resolve()
if out.exists():raise SystemExit('Choose a new output directory; archived evidence will not be overwritten.')
with tempfile.TemporaryFile() as combined:
 digest=hashlib.sha256()
 for part in manifest['parts']:
  content=(base/part['path']).read_bytes()
  if len(content)!=part['bytes'] or hashlib.sha256(content).hexdigest()!=part['sha256']:raise SystemExit('Part verification failed: '+part['path'])
  combined.write(content);digest.update(content)
 if digest.hexdigest()!=manifest['archive_sha256']:raise SystemExit('Combined archive verification failed')
 combined.seek(0)
 with tarfile.open(fileobj=combined,mode='r:gz') as archive:
  for member in archive.getmembers():
   rel=pathlib.PurePosixPath(member.name)
   if rel.is_absolute() or '..' in rel.parts or not member.isfile():raise SystemExit('Unexpected archive member: '+member.name)
  out.mkdir(parents=True)
  archive.extractall(out,filter='data')
 for row in manifest['files']:
  data=(out/row['path']).read_bytes()
  if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:raise SystemExit('Extracted file verification failed: '+row['path'])
print(f'Verified and extracted {len(manifest["files"])} files to {out}')
