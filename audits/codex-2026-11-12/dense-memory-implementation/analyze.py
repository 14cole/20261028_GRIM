"""Compare every returned complex field, preserving small numerical differences."""
import json
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent
rows=[]
def find(x,k):
 if isinstance(x,dict):
  if k in x:yield x[k]
  for v in x.values():yield from find(v,k)
 elif isinstance(x,list):
  for v in x:yield from find(v,k)
for path in sorted((p/'results').glob('*.json')):
 d=json.loads(path.read_text())
 if not isinstance(d,dict) or 'case' not in d or 'wall' not in d:continue
 row={k:d.get(k) for k in ('case','error','wall','peak_gib','rss_highwater_gib','backend','actual_unknowns','backend_source_sha256')}
 row['dense_paired']=d.get('paired')
 if d['error'] is None:
  a=np.load(p/'results'/(d['case']+'.npz'))['field']
  ref='airfoil-global' if d['body']=='airfoil' else 'pec8000' if d['body']=='pec' else 'coated9720'
  b=np.load(p/'references'/(ref+'.npz'))['field']
  assert a.shape==b.shape and np.isfinite(a).all()
  row.update(field_count=len(a),reference=ref,full_field_relative_error=float(np.max(abs(a-b))/np.max(abs(b))))
  row['strict_audit_comparison_threshold']=None if d['body']=='airfoil' else 1e-6 if d.get('mode')=='compressed' else 1e-11
  row['strict_audit_comparison_passed']=None if row['strict_audit_comparison_threshold'] is None else row['full_field_relative_error']<row['strict_audit_comparison_threshold']
  row['max_rcs_db_difference']=float(np.max(abs(20*np.log10(np.maximum(abs(a),1e-300)/np.maximum(abs(b),1e-300)))))
  if d.get('mode')=='compressed':
   for label in ('compressed-paired','compressed-unpaired'):
    c=np.load(p/'references'/(label+'.npz'))['field']
    row[label+'_relative_error']=float(np.max(abs(a-c))/np.max(abs(c)))
  meta=json.loads((p/'results'/(d['case']+'.npz.metadata.json')).read_text())
  plans=[v for v in find(meta,'memory_estimates')]
  row['actual_unknowns']=max(list(find(meta,'system_dofs'))+[d.get('actual_unknowns',0)])
  row['compressed_pair_choices']=sorted(set(v['paired_assembly'] for plan in plans for v in plan if v.get('model')=='compressed_hmatrix_v2'))
  row['dense_batch_sizes']=sorted(set(v['angle_batch_size'] for plan in plans for v in plan if v.get('model')=='dense_phase_v1'))
  row['dense_max_rhs_columns']=max(find(meta,'dense_max_rhs_columns'),default=0)
  row['certified']=meta.get('mesh_convergence_certified')
  row['max_panel_kl']=max((q['maximum_panel_kl'] for group in find(meta,'quadrature_qualification') for q in group),default=None)
  gates=list(find(meta,'quality_gate'));row['quality_passed']=bool(gates) and all(g['passed'] for g in gates)
  assert row['quality_passed'],row
 rows.append(row)
(p/'measurements.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
