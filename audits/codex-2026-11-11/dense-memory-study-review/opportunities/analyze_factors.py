import sys,json
from pathlib import Path
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent
rows=[json.loads(x) for x in (p/'factor-probes.jsonl').read_text().splitlines()]
summary=dict(attempts=len(rows),completed=sum(r['error'] is None for r in rows),rejected=[dict(fixture=Path(r['prefix']).name,method=r['method'],error=r['error']) for r in rows if r['error']],all_completed_backward_checks_pass=all(q['passes_dense_gate'] for r in rows if not r['error'] for q in r['results']),largest_completed_mixed_solution_difference=max(q.get('relative_solution_difference',0.) for r in rows if not r['error'] for q in r['results']),rows=rows)
(p/'factor-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2))
raise SystemExit(0 if summary['all_completed_backward_checks_pass'] else 1)
