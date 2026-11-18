"""Pack/replay complete results, including every measured complex field array."""
import pathlib,sys,json,hashlib,tarfile,shutil
root=pathlib.Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024**2),b''):h.update(block)
 return h.hexdigest()
if sys.argv[1]=='pack':
 evidence=root/'evidence';evidence.mkdir(exist_ok=True)
 paths=sorted((root/'results').glob('*'))+sorted(root.glob('check-dense-*.npz'))
 paths=[p for p in paths if p.is_file()]
 archive=root/'evidence.tar.gz'
 with tarfile.open(archive,'w:gz',compresslevel=6) as tar:
  for p in paths:tar.add(p,arcname=str(p.relative_to(root)))
 parts=[]
 with archive.open('rb') as f:
  for i,block in enumerate(iter(lambda:f.read(3*1024**2),b'')):
   p=evidence/f'evidence.tar.gz.part{i:03d}';p.write_bytes(block);parts.append(dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p)))
 manifest=dict(archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,parts=parts,members=[dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p)) for p in paths])
 (evidence/'manifest.json').write_text(json.dumps(manifest,indent=2));print('packed',len(paths),'files',len(parts),'parts',archive.stat().st_size,'bytes')
elif sys.argv[1]=='unpack':
 dest=pathlib.Path(sys.argv[2]);dest.mkdir(parents=True,exist_ok=True)
 assert not list(dest.iterdir()),'Use an empty destination'
 m=json.loads((root/'evidence/manifest.json').read_text());archive=dest/'evidence.tar.gz'
 with archive.open('wb') as output:
  for item in m['parts']:
   p=root/'evidence'/item['path'];assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'];output.write(p.read_bytes())
 assert sha(archive)==m['archive_sha256']
 with tarfile.open(archive,'r:gz') as tar:
  assert sorted(tar.getnames())==sorted(x['path'] for x in m['members'])
  tar.extractall(dest,filter='data')
 for item in m['members']:
  p=dest/item['path'];assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256']
 archive.unlink();print('verified',len(m['members']),'restored files')
else:raise ValueError('Use pack or unpack DESTINATION')
