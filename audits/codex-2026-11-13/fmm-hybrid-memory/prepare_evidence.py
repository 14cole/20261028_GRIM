"""Create a compact, explicitly scoped evidence copy; keep original full matrices locally."""
import pathlib,json,shutil,hashlib,numpy as np
src=pathlib.Path(__file__).parent;dst=pathlib.Path('/workspace/fmm-hybrid-evidence');dst.mkdir(exist_ok=False);scope=[]
for p in sorted(src.iterdir()):
 if not p.is_file() or p.suffix=='.pyc':continue
 if p.suffix=='.npz':
  z=np.load(p)
  if 'actual_matrix' in z:
   ref=z['reference_rows'];actual=z['actual_matrix'];delta=abs(actual-ref);flat=np.argpartition(delta.ravel(),-20)[-20:];rr,cc=np.unravel_index(flat,delta.shape);largest_ref=np.unravel_index(np.argmax(abs(ref)),ref.shape);columns=np.unique(np.r_[cc,largest_ref[1]])
   keep={k:z[k] for k in z.files if k not in ['actual_matrix','reference_rows']};keep.update(actual_columns=actual[:,columns],reference_columns=ref[:,columns],matrix_columns=columns,full_reference_max=np.max(abs(ref)),full_difference_max=delta.max(),full_reference_fro=np.linalg.norm(ref),full_difference_fro=np.linalg.norm(actual-ref));np.savez_compressed(dst/p.name,**keep)
   scope.append(dict(path=p.name,original_bytes=p.stat().st_size,original_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),matrix_shape=list(ref.shape),archived_columns=columns.tolist(),all_columns_tested=True,all_columns_archived=False));continue
 shutil.copy2(p,dst/p.name)
(dst/'FULL_MATRIX_ARCHIVE_SCOPE.json').write_text(json.dumps(scope,indent=2)+'\n');print('Evidence files',sum(p.is_file() for p in dst.iterdir()),'full-matrix files compacted',len(scope))
