import json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;rows=[]
for f in sorted((P/'results').glob('*.json')):
 if f.name.count('.')!=1:continue
 r=json.loads(f.read_text());s=r['spec'];row=dict(case=s['case'],model=s['geometry_id'],backend=s['backend'],variant=s.get('variant','baseline'),error=r.get('error'),wall_seconds=r['wall_seconds'],unknowns=r.get('actual_unknowns'),process_cpu_seconds=r.get('process_cpu_seconds'))
 monitor=json.loads(f.with_suffix('.monitor.json').read_text());row['peak_tree_rss_gib']=max(monitor['peak_tree_rss_gib'],r.get('rss_highwater_gib',0));row['termination']=monitor['termination']
 if r.get('error') is None:
  assert r['quality_gate']['passed'];x=np.load(f.with_suffix('.npz'))['field'];assert np.isfinite(x).all();row['quality_gate_passed']=True;row['fields']=len(x)
  for name,key in [(s['geometry_id']+'-dense-baseline','vs_dense'),(s['geometry_id']+'-'+s['backend']+'-baseline','vs_backend')]:
   ref=P/'results'/(name+'.npz')
   if ref.exists():
    y=np.load(ref)['field'];assert x.shape==y.shape
    samples=json.loads(f.with_suffix('.samples.json').read_text());ysamples=json.loads(ref.with_suffix('.samples.json').read_text());keys=['frequency_ghz','theta_inc_deg','theta_scat_deg','polarization']
    assert [[t[k] for k in keys] for t in samples]==[[t[k] for k in keys] for t in ysamples]
    row[key+'_relative_max_norm']=float(np.max(abs(x-y))/np.max(abs(y)))
  meta=json.loads(f.with_suffix('.metadata.json').read_text());row['stages']=meta.get('runtime_profile',{}).get('stage_seconds',{});row['condition_est_max']=meta.get('condition_est_max')
  row['peak_tree_rss_gib']=max(row['peak_tree_rss_gib'],meta.get('runtime_profile',{}).get('sampled_peak_process_tree_rss_bytes',0)/2**30)
  events=r.get('factor_events',[]);factor_times=[e['factor_work_seconds'] for e in events if e.get('factor_work_seconds') is not None];row['factor_work_seconds']=sum(factor_times) if factor_times else None;row['factor_variants']=[e.get('factor_variant') for e in events];row['factor_fallbacks']=[e.get('factor_fallback',False) for e in events]
  row['maximum_refinements']=max((e.get('max_refinements',0) for e in events),default=0)
  row['factorizations']=sum(e.get('factorizations',0) for e in events)
  row['retained_inverse_bytes']=[q.get('bytes') for e in events for q in e.get('preconditioners',[])]
  row['inverse_experiments']=r.get('experiment_records',[])
  row['max_backward_error']=max((e.get('max_backward_error',0) for e in events),default=0)
 rows.append(row)
summary=dict(cases=rows,successful=sum(r['error'] is None for r in rows),failed=sum(r['error'] is not None for r in rows))
(P/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
for r in rows:print(r['case'],round(r['wall_seconds'],2),round(r['peak_tree_rss_gib'],3),r.get('vs_dense_relative_max_norm'),r['error'])
