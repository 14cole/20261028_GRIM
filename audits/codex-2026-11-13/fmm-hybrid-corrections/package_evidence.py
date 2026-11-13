"""Compact full matrix archives, retain all fields, and create hashed XZ parts."""
import hashlib,json,shutil,tarfile,sys
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
OUT=Path(sys.argv[1]);E=Path(sys.argv[2]);OUT.mkdir(parents=True,exist_ok=True);E.mkdir(parents=True,exist_ok=True)
names='cached_fmm.py cached_galerkin.py hybrid_galerkin.py hybrid_galerkin_original.py safe_cross.py nodal_block.py moment_galerkin.py moment_hybrid.py fmm_galerkin.py fmm_native.py review_geometry.py combined_benchmark.py preconditioned_solve.py dense_control.py compressed_control.py check_safe_cross.py square_diag.py review_checks.py refine_stadium.py native_stadium_control.py run_investigation.py run_dense_after_suite.py run_square_baseline.py analyze_results.py write_handoff.py package_evidence.py'.split()
names+='ENVIRONMENT.json PRODUCTION_UNCHANGED.json SUMMARY.json HANDOFF_FMM_HYBRID_CORRECTIONS.md CLAUDE_TASKS.md REPRODUCTION.md'.split()
sha=lambda b:hashlib.sha256(b).hexdigest()
for name in names:shutil.copyfile(P/name,E/name);shutil.copyfile(P/name,OUT/name)
shutil.copytree(P/'claude_reference',E/'claude_reference',dirs_exist_ok=True)
shutil.copytree(P/'claude_reference',OUT/'claude_reference',dirs_exist_ok=True)
(E/'results').mkdir(exist_ok=True);scope=[]
for p in sorted((P/'results').iterdir()):
 if not p.is_file():continue
 dest=E/'results'/p.name
 if p.suffix=='.npz':
  with np.load(p) as z:
   if 'actual_matrix' in z:
    arrays=dict(z);a=arrays.pop('actual_matrix');b=arrays.pop('reference_rows');err=abs(a-b)
    columns=np.unique(np.r_[np.unravel_index(np.argpartition(err.ravel(),-32)[-32:],err.shape)[1],np.unravel_index(np.argmax(abs(b)),b.shape)[1]])
    arrays.update(matrix_columns=columns,actual_matrix_columns=a[:,columns],reference_matrix_columns=b[:,columns])
    np.savez_compressed(dest,**arrays)
    scope.append(dict(path=str(p.relative_to(P)),original_npz_bytes=p.stat().st_size,original_npz_sha256=sha(p.read_bytes()),shape=list(a.shape),retained_columns=columns.tolist(),full_matrix_test_completed=True,retained_full_matrix=False))
    continue
 shutil.copyfile(p,dest)
scope_doc=dict(policy='Full solve fields/densities and operator products retained. Full matrix archives reduced to columns containing 32 largest discrepancies plus a maximum reference entry. Rerun for full Frobenius norms/unseen entries.',files=scope)
for base in [E,OUT]:(base/'FULL_MATRIX_ARCHIVE_SCOPE.json').write_text(json.dumps(scope_doc,indent=2)+'\n')
identities={name:sha((E/name).read_bytes()) for name in names if name.endswith('.py')}
for base in [E,OUT]:(base/'SOURCE_IDENTITIES.json').write_text(json.dumps(identities,indent=2)+'\n')
archive=P/'evidence.tar.xz'
files=[]
with tarfile.open(archive,'w:xz',preset=6) as tf:
 for p in sorted(E.rglob('*')):
  if not p.is_file():continue
  b=p.read_bytes();rel=str(p.relative_to(E));files.append(dict(path=rel,bytes=len(b),sha256=sha(b)))
  ti=tf.gettarinfo(str(p),arcname=rel);ti.uid=ti.gid=ti.mtime=0;ti.uname=ti.gname=''
  with p.open('rb') as f:tf.addfile(ti,f)
parts=[];folder=OUT/'evidence';folder.mkdir(exist_ok=True)
with archive.open('rb') as f:
 i=0
 while b:=f.read(1024**2):
  rel=f'evidence/part-{i:03d}.xz';(OUT/rel).write_bytes(b);parts.append(dict(path=rel,bytes=len(b),sha256=sha(b)));i+=1
manifest=dict(archive_bytes=archive.stat().st_size,archive_sha256=sha(archive.read_bytes()),parts=parts,files=files)
(OUT/'EVIDENCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(archive_bytes=manifest['archive_bytes'],parts=len(parts),files=len(files))))
