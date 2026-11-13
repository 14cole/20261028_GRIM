"""Recompute saved operator/field comparisons; handles full or compact evidence."""
import json,sys
from pathlib import Path
import numpy as np
root=Path(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parent)
records={};checks=[]
for p in sorted((root/'results').glob('*.json')):
 if not p.stat().st_size or p.name.endswith('-spec.json'):continue
 try:d=json.loads(p.read_text())
 except json.JSONDecodeError:continue
 if not isinstance(d,dict):continue
 records[p.stem]=d
 if 'errors' in d:
  for kind,claimed in d['errors'].items():
   f=root/'results'/(p.stem+'-'+kind+'.npz')
   with np.load(f) as a:
    err=float(np.max(abs(a['actual'][a['rows']]-a['exact']))/np.max(abs(a['exact'])))
    assert np.isclose(err,claimed['random_relative_max'],rtol=1e-8,atol=1e-25),(f,err,claimed)
    if 'actual_matrix' in a:
     ref=a['reference_rows'];actual=a['actual_matrix']
     me=float(np.max(abs(actual-ref))/np.max(abs(ref)))
     fro=float(np.linalg.norm(actual-ref)/np.linalg.norm(ref))
     assert np.isclose(fro,claimed['matrix_relative_fro'],rtol=1e-8,atol=1e-25)
    elif 'actual_matrix_columns' in a:
     ref=a['reference_matrix_columns'];actual=a['actual_matrix_columns']
     me=float(np.max(abs(actual-ref))/np.max(abs(ref)))
    else:me=None
    if me is not None:assert np.isclose(me,claimed['matrix_relative_max'],rtol=1e-8,atol=1e-25),(f,me,claimed)
   checks.append(str(f.relative_to(root)))
 if p.stem.startswith('pre-') and 'results' in d:
  assert all(r['status']==0 for r in d['results']), (p,d['results'])
  f=root/'results'/(p.stem+'.npz')
  with np.load(f) as a:
   residual=a['exact_rows']@a['density']-a['rhs'][a['rows']]
   err=np.max(abs(residual)/(np.sum(abs(a['exact_rows']),axis=1)[:,None]*np.max(abs(a['density']),axis=0)+abs(a['rhs'][a['rows']])),axis=0)
   expected=d.get('exact_sampled_rowwise_backward_error',d.get('exact_sampled_componentwise_backward_error'))
   # BLAS thread counts change summation rounding, so these machine-level
   # residuals are checked against a bound, not bitwise equality.
   assert np.max(err)<1e-12 and max(expected)<1e-12,(p,err,expected)
   dense=root/'results'/(p.stem+'-dense.npz')
   if dense.exists():
    with np.load(dense) as b:
     fe=float(np.max(abs(a['field']-b['field']))/np.max(abs(b['field'])))
     assert np.isclose(fe,d['field_relative_max_error'],rtol=1e-8,atol=1e-25),(p,fe)
  checks.append(str(f.relative_to(root)))
for kind in ['S','K','KP','W']:
 base=root/'results'/('matrix-stadium-1536-'+kind+'.npz')
 if not base.exists():continue
 with np.load(base) as a:
  reference_max=float(np.max(abs(a['reference_rows'] if 'reference_rows' in a else a['reference_matrix_columns'])))
 for digits in [12,14]:
  p=root/'results'/f'stadium-digits{digits}-{kind}.npz'
  if p.exists():
   with np.load(p) as a:err=float(np.max(abs(a['actual']-a['reference']))/reference_max)
   assert np.isclose(err,records['stadium_refinement']['digits'][str(digits)][kind]['relative_max'],rtol=1e-8,atol=1e-25)
   checks.append(str(p.relative_to(root)))
 if kind in ['K','KP']:
  for eps in [1e-12,1e-14]:
   p=root/'results'/f'native-stadium-{kind}-{eps}.npz'
   if p.exists():
    with np.load(p) as a:err=float(np.max(abs(a['actual']-a['reference']))/reference_max)
    assert np.isclose(err,records['native_stadium']['operators'][kind]['eps'][str(eps)]['selected_column_relative_max'],rtol=1e-8,atol=1e-25)
    checks.append(str(p.relative_to(root)))
comparison={}
rp=root/'results/dense-4096-TE-fmm-residual.npz'
if rp.exists():
 with np.load(rp) as a:
  physical=np.max(abs(a['residual']),axis=0)/(float(a['matrix_inf'])*np.max(abs(a['density']),axis=0)+np.max(abs(a['rhs']),axis=0))
  scaled=np.sum(abs(a['residual'])/a['row_scale'][:,None],axis=0)/(float(a['scaled_norm_1'])*np.sum(abs(a['density'])*a['column_scale'][:,None],axis=0)+np.sum(abs(a['rhs'])/a['row_scale'][:,None],axis=0))
  assert max(physical.max(),scaled.max())<1e-12
 checks.append(str(rp.relative_to(root)))
dense=root/'results/dense-4096-TE.npz'
if dense.exists():
 with np.load(dense) as a:
  for name in ['pre-4096-TE-loose','pre-4096-TE-verified','compressed-4096-TE']:
   p=root/'results'/(name+'.npz')
   if p.exists():
    with np.load(p) as b:
     assert np.array_equal(a['angles'],b['angles']) and np.array_equal(a['observation'],b['observation'])
     comparison[name]=dict(field_relative_max=float(np.max(abs(a['field']-b['field']))/np.max(abs(a['field']))),density_relative_max=float(np.max(abs(a['density']-b['density']))/np.max(abs(a['density']))))
     assert comparison[name]['field_relative_max']<1e-10,comparison[name]
repeat=root/'results/pre-4096-TE-verified.npz'
if repeat.exists():
 with np.load(repeat) as a,np.load(root/'results/pre-4096-TE-loose.npz') as b:
  assert np.array_equal(a['density'],b['density']), 'Repeat changed density; re-evaluate full-matrix residual evidence'
 comparison['verified_repeat_density_bitwise_equal']=True
summary=dict(verified_array_files=len(checks),verified=checks,large_dense_comparison=comparison,records=records)
(root/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(dict(verified_array_files=len(checks),large_dense_comparison=comparison),indent=2))
