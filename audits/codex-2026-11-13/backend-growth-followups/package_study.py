"""Content-addressed complete experiment evidence, with small verified parts."""
from pathlib import Path
import hashlib,json,tarfile,io,shutil,sys,platform,zipfile
import numpy as np,scipy
root=Path('.');out=root/'publication';out.mkdir(exist_ok=True)
files=[];payloads={}
paths=list((root/'results').rglob('*'))+[root/'libpaired_kernel.so']
for p in sorted(paths):
 if not p.is_file():continue
 data=p.read_bytes();sha=hashlib.sha256(data).hexdigest();row=dict(path=p.as_posix(),bytes=len(data),sha256=sha)
 boundaries={0,len(data)}
 if p.suffix=='.npz':
  with zipfile.ZipFile(io.BytesIO(data)) as archive:
   boundaries.add(archive.start_dir)
   for item in archive.infolist():
    pos=item.header_offset;start=pos+30+int.from_bytes(data[pos+26:pos+28],'little')+int.from_bytes(data[pos+28:pos+30],'little')
    boundaries.update((pos,start,start+item.compress_size))
 boundaries=sorted(boundaries);chunks=[]
 for a,b in zip(boundaries,boundaries[1:]):
  if a==b:continue
  chunk=data[a:b];key=hashlib.sha256(chunk).hexdigest();payloads.setdefault(key,chunk);chunks.append(key)
 row['chunks']=chunks;files.append(row)
with tarfile.open('evidence.tar.xz','w:xz',preset=3) as tar:
 def add(name,data):
  item=tarfile.TarInfo(name);item.size=len(data);item.mtime=0;item.mode=0o644;tar.addfile(item,io.BytesIO(data))
 add('index.json',json.dumps(dict(files=files),sort_keys=True).encode())
 for sha,data in sorted(payloads.items()):add('payload/'+sha,data)
raw=Path('evidence.tar.xz').read_bytes();parts=[]
for start in range(0,len(raw),1024**2):
 data=raw[start:start+1024**2];name=f'evidence.tar.xz.part{start//1024**2:03d}';(out/name).write_bytes(data);parts.append(dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
(out/'EVIDENCE_MANIFEST.json').write_text(json.dumps(dict(format='content-addressed-chunks-tar-xz-v2',archive_bytes=len(raw),archive_sha256=hashlib.sha256(raw).hexdigest(),parts=parts,files=files),indent=2))
# Executable drivers are kept separately for convenient reproduction. Local
# queue helpers and source-mutation generators are not reproduction interfaces.
for name in ['check_native_fallbacks.py','native-fallbacks.json','measure.py','compressed_control.py','fmm_galerkin.py','profile_growth.py','norms_benchmark.py','legacy_norms.py','check_norms.py','bor_hierarchical_probe.py','netlib_adjoint_probe.py','build_pair_kernel.py','native_pairs.py','native_fmm_control.py','validate_native_pairs.py','analyze_growth.py','package_study.py','write_handoff.py','paired_kernel.c','pack_pair_arrays.py','collect_environment.py','REPRODUCTION.md','HANDOFF_BACKEND_GROWTH.md']:
 shutil.copyfile(root/name,out/name)
for folder in ['fmm','claude','regression','calibration']:
 shutil.copytree(root/folder,out/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
shutil.copyfile('unpack_evidence.py',out/'unpack_evidence.py')
shutil.copyfile(root/'results/SUMMARY.json',out/'RESULTS_SUMMARY.json')
identity=dict(claude_commit='bc950e4e83de95e16a2b996ab05a52157fa6913e',accepted_commit='65ebfe6a146adeae32b2fbd3ac02ad913b34acce',publication_parent='964ecc028fe8fc5aa9e5ed742a38fbf789ecfa34',production_changes=['tools/GHOST/ghost_backend/compressed/hmatrix.py','tools/GHOST/ghost_backend/linalg/products.py'],production_native_files_unchanged=True,python=sys.version,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform(),blas_threads=1)
identity['production_sha256']={name:hashlib.sha256((root/'candidate'/name).read_bytes()).hexdigest() for name in identity['production_changes']}
(out/'SOURCE_IDENTITIES.json').write_text(json.dumps(identity,indent=2))
print(json.dumps(dict(files=len(files),parts=len(parts),archive_bytes=len(raw))))
