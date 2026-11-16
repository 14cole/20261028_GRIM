"""Check the pinned cancellation records without claiming a fresh 48-case rerun."""
import json
from pathlib import Path
R=Path(__file__).resolve().parent;summary=[]
for p in sorted((R/'claude/out').glob('*-t*.json')):
    d=json.loads(p.read_text());assert len(d['phases'])==6
    for e in d['phases']:
        assert e['raised']=='Cancel' and e['fired'] and e['recovered']
        assert not e['workers_alive_after'] and e['active_tasks_after']==0
        assert e['tasks_started_total']==e['tasks_finished_total']
        assert e['inverse_objects_alive_after_gc']==0 and e['operator_bytes_unchanged']
        assert e['backward_error']<1e-12
        if e['mode']=='same_factor':assert e['same_factor_inverse_is_none']
    summary.append(dict(file=p.name,unknowns=2*d['spec']['n'],threads=d['spec']['threads'],builder=d['spec']['builder'],
        cancellations=len(d['phases']),nonidentical=[dict(mode=e['mode'],target=e['target']) for e in d['phases'] if not e['bitwise_equal_control']],
        ledger_present=d['ledger_state_present'],max_backward_error=max(e['backward_error'] for e in d['phases'])))
assert len(summary)==8 and sum(x['cancellations'] for x in summary)==48
assert sum(len(x['nonidentical']) for x in summary)==2
out=dict(cases=summary,cancellations=48,nonidentical_recoveries=2,
    scope='Pinned record/source verification only; no full control NPZ arrays or cross-thread density hashes published in ecc046c.')
(R/'review-record-check.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
