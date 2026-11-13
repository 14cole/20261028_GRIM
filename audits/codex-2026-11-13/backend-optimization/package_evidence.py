"""Deterministic content-addressed archive; retain every physical field array."""
from pathlib import Path
import hashlib,json,tarfile,io,shutil
root=Path('.');out=root/'publication';out.mkdir(exist_ok=True)
excluded={'product-baseline-512.npz','product-candidate-512.npz'}
records=[];omitted=[];payloads={}
for p in sorted((root/'results').iterdir()):
 if not p.is_file():continue
 data=p.read_bytes();sha=hashlib.sha256(data).hexdigest();row=dict(path=p.as_posix(),bytes=len(data),sha256=sha)
 if p.name in excluded:
  row['reason']='Identical synthetic wide-RHS benchmark output; deterministic regeneration script and raw timings included.'
  omitted.append(row);continue
 records.append(row);payloads.setdefault(sha,p)
index=dict(files=records,omitted=omitted)
archive=root/'evidence.tar.xz'
with tarfile.open(archive,'w:xz',preset=3) as tar:
 def add(name,data):
  entry=tarfile.TarInfo(name);entry.size=len(data);entry.mtime=0;entry.mode=0o644;tar.addfile(entry,io.BytesIO(data))
 add('index.json',json.dumps(index,sort_keys=True,indent=2).encode())
 for sha,p in sorted(payloads.items()):add('payload/'+sha,p.read_bytes())
raw=archive.read_bytes();parts=[]
for i in range(0,len(raw),1024**2):
 name=f'evidence.tar.xz.part{i//1024**2:03d}';data=raw[i:i+1024**2];(out/name).write_bytes(data)
 parts.append(dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
manifest=dict(format='content-addressed-tar-xz-v1',archive_bytes=len(raw),archive_sha256=hashlib.sha256(raw).hexdigest(),parts=parts,**index)
(out/'EVIDENCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
for p in root.glob('*.py'):
 if p.name!='write_handoff.py':shutil.copyfile(p,out/p.name)
for name in ['native_unroll_experiment.c','native_simd_experiment.patch']:shutil.copyfile(root/name,out/name)
shutil.copyfile(root/'results/analysis.json',out/'RESULTS_SUMMARY.json')
print(json.dumps(dict(files=len(records),unique_payloads=len(payloads),archive_bytes=len(raw),parts=len(parts))))
