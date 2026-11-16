"""Replay pinned arrays, sparse coefficient differences and attribution records."""
import os,json,hashlib
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;D=Path(os.environ.get('RESULTS_DIR',str(R/'results')))
sha=lambda a:hashlib.sha256(a.tobytes(order='C')).hexdigest()
blob=lambda b:hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
p=json.loads((R/'source-provenance.json').read_text())
for f in p['files']:assert blob((R/'claude'/f['path']).read_bytes())==f['sha']
assert blob((R/'prior/star-control.npz').read_bytes())=='4449a2825ee3c50cc5b9bc0888ca38503e391bcc'
assert blob((R/'prior/control_array_hashes.json').read_bytes())=='3c5fa50f2c2ce43b694354072a19d25808dbf3a3'
manifest=json.loads((R/'claude/first_two_arrays/hashes_both_trees.json').read_text());configs=[]
for file in sorted((R/'claude/first_two_arrays').glob('*.npz')):
 label=file.stem.removesuffix('-first-two');a=manifest['orig/'+label];b=manifest['fixed/'+label];assert a==b
 with np.load(file) as z:
  for k,v in b.items():assert list(z[k].shape)==v['shape'] and sha(z[k])==v['sha256_c_order']
 configs.append(label)
control=np.load(R/'prior/star-control.npz');saved=np.load(R/'claude/star_residuals/star8192-residuals-t1-and-t4.npz')
prior=json.loads((R/'prior/control_array_hashes.json').read_text())
for t in [1,4]:assert sha(saved['residual_t'+str(t)])==prior['star8192-production-t'+str(t)]['residual']['sha256_c_order']
den=control['row_norm'][:,None]*np.max(abs(control['density']),axis=0)+abs(control['rhs'][control['rows']])
diff=abs(saved['residual_t4']-saved['residual_t1'])
residual=dict(different_entries=int(np.count_nonzero(diff)),entries=diff.size,max_abs_difference=float(diff.max()),max_denominator_normalized_difference=float(np.max(diff/den)),
 backward_t1=float(np.max(abs(saved['residual_t1'])/den)),backward_t4=float(np.max(abs(saved['residual_t4'])/den)))
assert residual['different_entries']==349 and residual['max_denominator_normalized_difference']<2e-19
rows=json.loads((D/'rows.json').read_text());published=json.loads((R/'claude/star_residuals/exact_row_threads.json').read_text())
with np.load(D/'row-evidence.npz') as z:
 for x in rows:
  label=x['label'];a=z[label+'_reference_values'];b=z[label+'_values'];indices=z[label+'_changed_flat_indices'];d=abs(b-a)
  assert len(indices)==x['different_entries'] and np.all(indices>=0) and np.all(indices<x['entries']) and len(np.unique(indices))==len(indices)
  assert (float(d.max()) if len(d) else 0.)==x['max_abs_coefficient_difference']
  assert (float(np.max(d/abs(a))) if len(d) else 0.)==x['max_relative_changed_entry']
  res=z[label+'_residual'];assert sha(res)==x['residual_sha256']
  assert all(pool['threads']==x['blas_threads'] for pool in x['blas_pools'])
  c=published[str(x['assembly_threads'])]
  assert x['exact_sha256'].startswith(c['sha256']) and x['different_entries']==c['entries_differing'] and x['max_abs_coefficient_difference']==c['max_abs_diff']
  den2=z[label+'_row_norm'][:,None]*np.max(abs(control['density']),axis=0)+abs(control['rhs'][control['rows']])
  assert float(np.max(abs(res)/den2))==x['max_backward_error']<1e-12
partition=json.loads((D/'partition.json').read_text());by={x['label']:x for x in partition}
assert by['default1']['exact_sha256']==by['workers4_tiles1']['exact_sha256']
assert by['default4']['exact_sha256']==by['workers1_tiles4']['exact_sha256']==by['workers4_tiles4_serial_commit']['exact_sha256']
grading=json.loads((D/'grading.json').read_text())
with np.load(D/'grading-evidence.npz') as z:
 a=z['reference_values'];b=z['values'];assert len(a)==grading['different_entries'];assert (float(np.max(abs(a-b))) if len(a) else 0.)==grading['max_abs_difference']
 for x in grading['cases']:assert sha(z['residual'+str(x['threads'])])==x['residual_sha256']
out=dict(claude_blobs_verified=len(p['files']),prior_blobs_verified=2,first_stable_configurations_verified=configs,saved_residual_difference=residual,
 fresh_row_queries=len(rows),fresh_partition_queries=len(partition),fresh_ungraded_queries=len(grading['cases']),blas_pools_verified=True,
 coefficient_results_reproduce_claude=True,fixed_tile_policy_removes_thread_difference=True,ungraded_comparison=grading,
 production_changes=0,new_solver_runs=0,scope='One Linux native library, 96 rows of one dielectric star; full row matrices compared in memory, sparse differences/residuals archived. No independent cross-thread operator or field assembly.')
Path(os.environ.get('ANALYSIS_OUT',str(R/'analysis.json'))).write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
