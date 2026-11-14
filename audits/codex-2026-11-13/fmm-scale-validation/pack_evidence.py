"""Hash-verified archive; deduplicate exact ZIP members without altering files."""
import io,tarfile,hashlib,json,zipfile
from pathlib import Path

def pack(paths,prefix,manifest):
 out=Path('publication');out.mkdir(exist_ok=True);files=[];payloads={}
 for p in sorted(paths):
  data=p.read_bytes();sha=hashlib.sha256(data).hexdigest();bounds={0,len(data)}
  if p.suffix=='.npz':
   with zipfile.ZipFile(io.BytesIO(data)) as z:
    bounds.add(z.start_dir)
    for info in z.infolist():
     pos=info.header_offset;start=pos+30+int.from_bytes(data[pos+26:pos+28],'little')+int.from_bytes(data[pos+28:pos+30],'little')
     bounds.update((pos,start,start+info.compress_size))
  bounds=sorted(bounds);chunks=[]
  for a,b in zip(bounds,bounds[1:]):
   if a==b:continue
   chunk=data[a:b];key=hashlib.sha256(chunk).hexdigest();payloads.setdefault(key,chunk);chunks.append(key)
  files.append(dict(path=p.as_posix(),bytes=len(data),sha256=sha,chunks=chunks))
 archive=Path(prefix+'.tar.xz')
 with tarfile.open(archive,'w:xz',preset=3) as tar:
  def add(name,data):
   item=tarfile.TarInfo(name);item.size=len(data);item.mtime=0;item.mode=0o644;tar.addfile(item,io.BytesIO(data))
  add('index.json',json.dumps(dict(files=files),sort_keys=True).encode())
  for sha,data in sorted(payloads.items()):add('payload/'+sha,data)
 raw=archive.read_bytes();parts=[]
 for start in range(0,len(raw),1024**2):
  data=raw[start:start+1024**2];name=f'{prefix}.tar.xz.part{start//1024**2:03d}';(out/name).write_bytes(data);parts.append(dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
 (out/manifest).write_text(json.dumps(dict(format='content-addressed-chunks-tar-xz-v2',archive_bytes=len(raw),archive_sha256=hashlib.sha256(raw).hexdigest(),parts=parts,files=files),indent=2))
 print(json.dumps(dict(manifest=manifest,files=len(files),archive_bytes=len(raw),parts=len(parts))),flush=True)
if __name__=='__main__':
 import sys
 if sys.argv[1]=='baseline':pack(list(Path('results').glob('fmm-32768.*')),'baseline-evidence','BASELINE_EVIDENCE_MANIFEST.json')
 else:
  old={f['path'] for f in json.loads(Path('publication/BASELINE_EVIDENCE_MANIFEST.json').read_text())['files']}
  paths=[p for p in Path('results').rglob('*') if p.is_file() and p.as_posix() not in old]+[Path('libpaired_kernel.so')]
  pack(paths,'evidence','EVIDENCE_MANIFEST.json')
