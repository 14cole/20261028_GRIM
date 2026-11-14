"""Fetch pinned public GitHub evidence and verify Git blob hashes."""
import hashlib,json,urllib.request
from pathlib import Path
j=json.loads(Path('source_manifest.json').read_text());cache={}
for f in j['files']:
 p=Path('source')/f['path'];p.parent.mkdir(parents=True,exist_ok=True)
 if f['sha'] in cache:data=cache[f['sha']]
 elif p.exists():data=p.read_bytes()
 else:
  url='https://raw.githubusercontent.com/'+j['repository']+'/'+j['commit']+'/'+f['path']
  with urllib.request.urlopen(url,timeout=60) as response:data=response.read(f['size']+1)
 assert len(data)==f['size'],f['path']
 assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==f['sha'],f['path']
 p.write_bytes(data);cache[f['sha']]=data
 print('Verified',f['path'],len(data),flush=True)
