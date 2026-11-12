import json,statistics
from pathlib import Path
P=Path(__file__).resolve().parent;data=json.loads((P/'SUMMARY.json').read_text())['cases'];groups={}
notes=json.loads((P/'RUN_NOTES.json').read_text()) if (P/'RUN_NOTES.json').exists() else {}
for r in data:
 if r['error'] or notes.get(r['case'],{}).get('exclude_from_timing_summary'):continue
 source=json.loads((P/'results'/(r['case']+'.json')).read_text())
 if source['spec'].get('capture_matrix'):continue
 key=(r['model'],r['backend'],r['variant']);groups.setdefault(key,[]).append(r)
rows=[]
for (model,backend,variant),g in groups.items():
 if len(g)<2:continue
 def stats(key):
  v=[r[key] for r in g if r.get(key) is not None];return dict(count=len(v),median=statistics.median(v),minimum=min(v),maximum=max(v)) if v else None
 rows.append(dict(model=model,backend=backend,variant=variant,cases=[r['case'] for r in g],wall_seconds=stats('wall_seconds'),peak_rss_gib=stats('peak_tree_rss_gib'),process_cpu_seconds=stats('process_cpu_seconds'),factor_work_seconds=stats('factor_work_seconds')))
(P/'TIMING_REPEATS.json').write_text(json.dumps(dict(capture_runs_excluded=True,groups=rows),indent=2)+'\n')
print(json.dumps(rows,indent=2))
