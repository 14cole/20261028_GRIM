"""Full-array and raw-record validation of actual production integration."""
import os,json,hashlib
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;D=Path(os.environ.get('RESULTS_DIR',str(R/'results')))
def arrays(label):
 with np.load(D/(label+'-batch0000.npz')) as z:return {k:z[k] for k in z.files}
def comparison(label,reference):
 a,b=arrays(label),arrays(reference);result={}
 for key in ('density','rhs','field'):
  x,y=a[key],b[key];assert x.shape==y.shape and x.dtype==y.dtype
  diff=x-y
  rel=float(np.max(np.linalg.norm(diff,axis=0)/np.maximum(np.linalg.norm(y,axis=0),1e-300))) if x.ndim==2 else float(np.linalg.norm(diff)/max(np.linalg.norm(y),1e-300))
  result[key]=dict(bit_identical=x.tobytes()==y.tobytes(),relative_l2=rel,peak_normalized=float(np.max(abs(diff))/max(np.max(abs(y)),1e-300)))
 assert result['rhs']['bit_identical'] and result['density']['relative_l2']<1e-7 and result['field']['peak_normalized']<1e-7,(label,reference,result)
 return result
specs={}
for suite in R.glob('suite_*.json'):specs.update(json.loads(suite.read_text()))
records={};summaries={}
for label,spec in specs.items():
 a=json.loads((D/(label+'.json')).read_text());timing=json.loads((D/(label+'.time.json')).read_text())
 assert timing['returncode']==0 and not a.get('error'),(label,a.get('error'))
 assert a['pending_after']==0 and not a['workers_after']
 z=arrays(label);assert all(np.isfinite(x).all() for x in z.values())
 den=z['row_norm'][:,None]*np.max(abs(z['density']),axis=0)+abs(z['rhs'][z['rows']]);back=float(np.max(abs(z['residual'])/den));assert back<1e-12
 if spec.get('condition',True):assert np.isfinite(a['diagnostics']['condition_est'])
 if 'cancel' in spec:
  c=a['cancel_cleanup'];assert c['pending_bytes']==c['live_failed_inverses']==c['active']==0 and not c['workers'] and c['executor_reset']
  if spec.get('active_cancel'):assert a['cancel_active_at_checkpoint']>0
 if spec.get('fallback'):assert a['faults'] and any(p['dense_fallbacks']>0 for p in a['event']['preconditioners'])
 records[label]=a
 summaries[label]=dict(spec=spec,compute_seconds=a['compute_seconds'],stages=a['stages'],compute_peak_gib=a['compute_peak_gib'],peak_gib=a['peak_gib'],
  backward_error=back,build_tolerances=a['build_tolerances'],refinement_steps=a['event'].get('refinement_steps',0),gmres_columns=a['event'].get('gmres_columns',0),
  final_inverse_bytes=(a['event'].get('preconditioners') or [{}])[-1].get('bytes'),
  construction_peak_accounted=max((p['construction']['peak_accounted_build_bytes'] for p in a['event'].get('preconditioners',[])),default=0),
  array_hashes={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in z.items()})
pairs={}
for group in ('star','slot','pec'):
 for variant in ('baseline','candidate'):pairs[group+'-'+variant+' vs Dense']=comparison(group+'-'+variant,group+'-dense')
 c=comparison(group+'-candidate',group+'-baseline');assert all(v['bit_identical'] for v in c.values());pairs[group+' candidate vs baseline']=c
for label in ['star-candidate-t1','star-cancel-products','star-cancel-products-active','star-cancel-child','star-cancel-woodbury']:
 c=comparison(label,'star-candidate');assert all(v['bit_identical'] for v in c.values());pairs[label+' vs ordinary']=c
c=comparison('star-candidate-fallback','star-baseline-fallback');assert all(v['bit_identical'] for v in c.values());pairs['matched forced fallback']=c
for rep in (1,2):
 c=comparison(f'medium-candidate-{rep}',f'medium-baseline-{rep}');assert all(v['bit_identical'] for v in c.values());pairs['medium matched '+str(rep)]=c
pairs['32k cap candidate vs baseline']=comparison('cap32k-candidate','cap32k-baseline')
performance={}
for name,base,candidate in [('medium',['medium-baseline-1','medium-baseline-2'],['medium-candidate-1','medium-candidate-2']),('cap32k',['cap32k-baseline'],['cap32k-candidate'])]:
 b=float(np.median([summaries[x]['compute_seconds'] for x in base]));c=float(np.median([summaries[x]['compute_seconds'] for x in candidate]))
 performance[name]=dict(samples_each=len(base),baseline_seconds=b,candidate_seconds=c,time_reduction_percent=100*(1-c/b),
  baseline_peak_gib=[summaries[x]['compute_peak_gib'] for x in base],candidate_peak_gib=[summaries[x]['compute_peak_gib'] for x in candidate])
out=dict(cases=summaries,comparisons=pairs,performance=performance,all_pass=True,completed_field_solves=len(records),
 max_exact_backward_error=max(x['backward_error'] for x in summaries.values()),scope='Algebraic agreement and 96 exact rows; no mesh certification, full GUI validation, or 32 GB pressure test.')
Path(os.environ.get('ANALYSIS_OUT',str(R/'analysis.json'))).write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k not in ('cases','comparisons')},indent=2))
