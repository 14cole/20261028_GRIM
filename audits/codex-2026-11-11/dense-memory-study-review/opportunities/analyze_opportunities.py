import sys,json,statistics
from pathlib import Path
import numpy as np
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent
rows=[json.loads(x) for x in (p/'memory-options.jsonl').read_text().splitlines()];checked=[]
for r in rows:
 d={k:r.get(k) for k in ('case','body','wall','rss_highwater_gib','error','paired','quality_gate','trim_events')}
 if r['error'] is None:
  a=np.load(p/'runs'/(r['case']+'.npz'))['field'];b=np.load(p/'runs'/(r['body']+'-baseline.npz'))['field']
  d.update(full_field_relative_error=float(np.max(abs(a-b))/np.max(abs(b))),field_count=len(a),threshold=1e-11)
  d['passed']=d['full_field_relative_error']<d['threshold'] and r['quality_gate']['passed'] and not r['paired']
 checked.append(d)
summary={}
for body in ('pec','coated'):
 baseline=[r for r in checked if r['body']==body and 'baseline' in r['case']]
 combined=[r for r in checked if r['body']==body and 'combined' in r['case']]
 if combined:
  summary[body]={kind:dict(repeats=len(values),median_seconds=statistics.median(r['wall'] for r in values),rss_range_gib=[min(r['rss_highwater_gib'] for r in values),max(r['rss_highwater_gib'] for r in values)],median_rss_gib=statistics.median(r['rss_highwater_gib'] for r in values)) for kind,values in [('baseline',baseline),('combined',combined)]}
  b,c=summary[body]['baseline'],summary[body]['combined'];summary[body].update(rss_reduction_fraction=1-c['median_rss_gib']/b['median_rss_gib'],runtime_increase_fraction=c['median_seconds']/b['median_seconds']-1)
geometry=[]
if (p/'geometry.jsonl').exists():
 ref=np.load(p/'geometry/merged-ppw160.npz')['field']
 for line in (p/'geometry.jsonl').read_text().splitlines():
  r=json.loads(line)
  if r['error'] is None:
   a=np.load(p/'geometry'/(r['case']+'.npz'))['field'];mask=abs(ref)>np.max(abs(ref))*1e-3
   r['relative_field_difference_to_ppw160']=float(np.max(abs(a-ref))/np.max(abs(ref)))
   r['max_rcs_db_difference_to_ppw160_above_minus60db']=float(np.max(abs(20*np.log10(np.maximum(abs(a[mask]),1e-300)/abs(ref[mask])))))
   r['field_count']=len(a)
  geometry.append(r)
result=dict(memory_attempts=len(checked),memory_checks=checked,shortlist=summary,geometry=geometry)
(p/'opportunity-summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(memory_attempts=len(checked),all_fields_pass=all(r.get('passed',False) for r in checked),largest_field_difference=max(r.get('full_field_relative_error',0) for r in checked),shortlist=summary,geometry=[{k:r.get(k) for k in ('case','factors','relative_field_difference_to_ppw160','max_rcs_db_difference_to_ppw160_above_minus60db','error')} for r in geometry]),indent=2))
raise SystemExit(0 if all(r.get('passed',False) for r in checked) else 1)
