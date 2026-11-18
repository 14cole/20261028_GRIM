import pathlib,urllib.request,hashlib,json,concurrent.futures
root=pathlib.Path(__file__).resolve().parent
prefix='audits/claude-2026-11-18/postmerge-optimization-review/'
files=json.loads((root/'claude-inventory.json').read_text())
def fetch(e):
 p=root/'claude'/e['path'][len(prefix):];p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():
  d=p.read_bytes()
  if hashlib.sha1(b'blob '+str(len(d)).encode()+b'\0'+d).hexdigest()==e['sha']:return
 d=urllib.request.urlopen('https://raw.githubusercontent.com/14cole/20261028_GRIM/df18342afb09cd6c6cd3b954c5ef1d8afb3b3894/'+e['path'],timeout=60).read()
 assert hashlib.sha1(b'blob '+str(len(d)).encode()+b'\0'+d).hexdigest()==e['sha'],e['path']
 p.write_bytes(d)
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:list(pool.map(fetch,files))
print('verified',len(files),'files at df18342')
