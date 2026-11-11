import sys,json,statistics
from pathlib import Path
import numpy as np
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent
rows=[json.loads(s) for s in (p/'airfoil-adaptive.jsonl').read_text().splitlines()]
ref=np.load(p/'airfoil/global.npz')['field'];results=[]
for r in rows:
 d={k:r.get(k) for k in ('case','wall','rss_highwater_gib','error','hp_coarsening')}
 if not r['error']:
  a=np.load(p/'airfoil'/(r['case']+'.npz'))['field'];m=json.loads((p/'airfoil'/(r['case']+'.npz.metadata.json')).read_text())
  d.update(unknowns=[e['n'] for e in r['events'] if e['event']=='factor_init_begin'],quality_gate=m['quality_gate'],mesh_convergence_certified=m.get('mesh_convergence_certified',False),polynomial_degree=m.get('polynomial_degree'),warnings=m.get('warnings',[]),relative_field_difference=float(np.max(abs(a-ref))/np.max(abs(ref))))
  mask=abs(ref)>np.max(abs(ref))*1e-3
  d['max_rcs_db_difference_above_minus60db']=float(np.max(abs(20*np.log10(abs(a[mask])/abs(ref[mask])))))
  d['compared_rcs_samples']=int(mask.sum());d['quadrature_warning']=any('Electrically long panels' in v for v in d['warnings'])
  d['mesh_convergence']=m.get('mesh_convergence')
 results.append(d)
summary={}
for name in ('global','adaptive-certified'):
 group=[r for r in results if r['case'] in (name,name+'-repeat')]
 summary[name]=dict(repeats=len(group),median_seconds=statistics.median(r['wall'] for r in group),median_rss_gib=statistics.median(r['rss_highwater_gib'] for r in group),rss_range_gib=[min(r['rss_highwater_gib'] for r in group),max(r['rss_highwater_gib'] for r in group)])
(p/'airfoil-summary.json').write_text(json.dumps(dict(summary=summary,runs=results),indent=2)+'\n')
print(json.dumps(dict(summary=summary,runs=[{k:r.get(k) for k in ('case','unknowns','wall','rss_highwater_gib','relative_field_difference','max_rcs_db_difference_above_minus60db','mesh_convergence_certified','quadrature_warning','error')} for r in results]),indent=2))
