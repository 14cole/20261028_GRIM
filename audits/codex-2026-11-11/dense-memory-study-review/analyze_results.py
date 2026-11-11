"""Validate every recorded field, summarize repetitions and preserve failures."""
import json,sys
from pathlib import Path
import numpy as np
p=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).parent
rows=[]
for name in ('independent','diagnostic'):
 f=p/(name+'.jsonl')
 if f.exists():
  for line in f.read_text().splitlines():
   row=json.loads(line);row['series']=name;rows.append(row)
def group(r):
 if r['body']=='airfoil':return 'airfoil3'
 if r['body']=='coated':return 'coated9720'
 if r['body']=='diel':return 'diel8'
 return 'pec'+str(r['n']//1000)
references={}
for name in ('pec8','coated9720','airfoil3','pec14','diel8'):
 f=p/'runs'/(name+'-default-0.npz')
 if f.exists():references[name]=np.load(f)['field']
comparisons=[]
for r in rows:
 if r['error'] is not None:continue
 f=p/('runs' if r['series']=='independent' else 'diagnostics')/(r['case']+'.npz');a=np.load(f)['field'];b=references[group(r)]
 assert a.shape==b.shape and np.isfinite(a).all(),r['case']
 error=float(np.max(abs(a-b))/max(np.max(abs(b)),1e-300))
 limit=1e-6 if r.get('backend')!='cpu' else 1e-11
 # Retain failures as findings; never relax the declared comparison threshold.
 agreement=error<limit
 assert r.get('quality_gate',{}).get('passed'),(r['case'],r.get('quality_gate'))
 comparisons.append(dict(case=r['case'],body=group(r),samples=len(a),relative_error=error,threshold=limit,bitwise_equal=bool(np.array_equal(a,b)),backend=r.get('backend'),quality_passed=True,field_check_passed=agreement))
groups={}
for r in rows:
 if r['error'] is not None or r.get('lean_forecast') or r.get('trace_allocations') or r.get('chunk_projection'):continue
 name=r['case'].rsplit('-',1)[0] if r['case'].endswith(('-0','-1')) else r['case']
 groups.setdefault(name,[]).append(r)
summary={}
for name,rs in groups.items():
 summary[name]=dict(runs=len(rs),wall_median=float(np.median([r['wall'] for r in rs])),wall_range=[min(r['wall'] for r in rs),max(r['wall'] for r in rs)],
   rss_gib_range=[min(r['rss_highwater_gib'] for r in rs),max(r['rss_highwater_gib'] for r in rs)],
   rss_growth_gib_range=[min(r['rss_highwater_gib']-r['base_gib'] for r in rs),max(r['rss_highwater_gib']-r['base_gib'] for r in rs)],
   cgroup_growth_gib_range=[min((r['peak_cgroup']['current']-r['base_cgroup']['current'])/2**30 for r in rs),max((r['peak_cgroup']['current']-r['base_cgroup']['current'])/2**30 for r in rs)],
   storage=[[e.get('storage') for e in r['events'] if e['event']=='factor_init_end'] for r in rs])
report=dict(attempts=len(rows),completed_solves=len(comparisons),field_checks_passed=sum(x['field_check_passed'] for x in comparisons),field_checks_failed=sum(not x['field_check_passed'] for x in comparisons),failures=[dict(case=r['case'],error=r['error'],rejected=r.get('rejected'),pair_plans=r.get('pair_plans'),experimental_forecast=r.get('experimental_forecast')) for r in rows if r['error']],
 comparisons=comparisons,groups=summary)
(p/'comparison-summary.json').write_text(json.dumps(report,indent=2)+'\n')
print('Attempts:',len(rows),'completed solves compared:',len(comparisons),'recorded refusals:',len(report['failures']))
print('Largest dense relative field difference:',max((x['relative_error'] for x in comparisons if x['backend']=='cpu'),default=0))
print('Largest compressed relative field difference:',max((x['relative_error'] for x in comparisons if x['backend']!='cpu'),default=0))
for name,s in summary.items():print(name,s['runs'],round(s['wall_median'],2),[round(x,3) for x in s['rss_gib_range']])

failed=[x for x in comparisons if not x['field_check_passed']]
for x in failed:print('FIELD COMPARISON FAILED',x['case'],x['relative_error'],x['threshold'])
sys.exit(bool(failed))
