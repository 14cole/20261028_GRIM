"""Recompute comparisons directly from archived complete arrays."""
import json
from pathlib import Path
import numpy as np
root=Path('results');out={}
for label,a,b in [('fmm_vs_adaptive_65536','fmm-65536','adaptive-65536'),('adaptive_vs_compressed_32768','adaptive-32768','compressed-32768'),('adaptive_vs_fmm_32768','adaptive-32768','fmm-32768'),('fmm_vs_compressed_65536','fmm-65536','compressed-65536'),('fmm_vs_compressed_32768','fmm-32768','compressed-32768'),('mixed_vs_fmm_32768','storage-32768-te','fmm-32768'),('mixed_vs_compressed_32768','storage-32768-te','compressed-32768'),*[(f'{case}_vs_dense',f'storage-4096-{case}',f'storage-4096-{case}-dense') for case in ['te','tm','lossy']]]:
 if not all((root/(x+'.npz')).exists() for x in [a,b]):continue
 aa=np.load(root/(a+'.npz'));bb=np.load(root/(b+'.npz'));record={}
 for key in ['angles','observation','rhs']:
  if key in aa and key in bb:assert np.array_equal(aa[key],bb[key]),(label,key)
 for key in ['density','field']:
  x,y=aa[key],bb[key];assert np.all(np.isfinite(x)) and x.shape==y.shape
  record[key+'_relative_2']=float(np.linalg.norm(x-y)/np.linalg.norm(y))
  record[key+'_relative_max']=float(np.max(abs(x-y))/np.max(abs(y)))
 assert record['field_relative_max']<1e-10,(label,record)
 if label.endswith('_vs_dense'):
  j=json.loads((root/(a+'.json')).read_text())
  assert record['density_relative_2']<1e-8,(label,record)
  assert j['dense_full_backward_error']<1e-12 and j['dense_full_relative_residual']<1e-8,(label,j)
  record['dense_full_backward_error']=j['dense_full_backward_error']
  record['dense_full_relative_residual']=j['dense_full_relative_residual']
 out[label]=record
out['measurements']={}
for p in sorted(root.glob('*.time.json')):
 label=p.name.removesuffix('.time.json');data=json.loads(p.read_text());record={k:data[k] for k in ['rc','wall_seconds','peak_gib']}
 if data['rc']==0 and (root/(label+'.json')).exists():
  r=json.loads((root/(label+'.json')).read_text())
  for key in ['validated_solve_seconds','peak_preconditioner_gib','fmm_setup_seconds','solve_seconds','operator_bytes','inverse_bytes','fmm_bytes','exact_sampled_rowwise_backward_error','field_relative_max_error','unseen_components','preconditioner_storage_evidence','validation_queries','adaptive_sketch_evidence']:
   if key in r:record[key]=r[key]
  if 'results' in r:record['iterations']=[x['iterations'] for x in r['results']]
 out['measurements'][label]=record
composition={}
for name in ['compressed-32768','compressed-65536','adaptive-32768','adaptive-65536','fmm-32768','fmm-65536','storage-32768-te']:
 if not (root/(name+'.json')).exists():continue
 j=json.loads((root/(name+'.json')).read_text());e=j['operator_evidence']
 composition[name]={key:e[key] for key in ['retained_bytes','near_bytes','far_bytes','sample_row_storage_bytes']}
 if 'preconditioner_reachable_array_bytes' in j:composition[name]['live_inverse_plus_fmm_bytes']=j['preconditioner_reachable_array_bytes']+j['fmm_bytes']
Path('results/operator-composition.json').write_text(json.dumps(composition,indent=2))
Path('results/comparisons.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
