"""Fetch immutable reviewer NPZ artifacts and verify their Git blob identities."""
import hashlib,json,urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
R=Path(__file__).resolve().parent
m=json.loads((R/'binary-provenance.json').read_text())
def fetch(f):
    url='https://raw.githubusercontent.com/14cole/20261028_GRIM/'+m['commit']+'/'+m['prefix']+f['path']
    p=R/'claude'/f['path'];p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():data=p.read_bytes()
    else:
        with urllib.request.urlopen(url,timeout=30) as response:data=response.read()
    assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==f['sha']
    if not p.exists():p.write_bytes(data)
    return dict(path=f['path'],bytes=len(data),git_blob_verified=True)
if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(fetch,m['files']))
    (R/'download-verification.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))
