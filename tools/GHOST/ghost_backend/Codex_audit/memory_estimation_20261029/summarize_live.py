"""Summarize the real run's instrumentation; preserve raw events."""
import json
from audit import HERE, ROOT, GIB, walk

directory=HERE/'live_inlet15'
events=[json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
metadata=json.loads((directory/'metadata.json').read_text())
monitor=json.loads((directory/'monitor.json').read_text())
plans=[v for v in walk(metadata) if 'phase_bytes' in v and 'peak_bytes' in v]
storage=[e for e in events if e['kind']=='automatic_storage']
factors=[e for e in events if e['kind']=='factor_finish']
stages={}
for row in events:
    if row['kind']!='stage':continue
    event=row['event'];key=event['stage_key']
    value=stages.setdefault(key,dict(sample_count=0,peak_tree_rss_bytes=0,peak_tree_private_commit_bytes=0))
    value['sample_count']+=1
    value['peak_tree_rss_bytes']=max(value['peak_tree_rss_bytes'],event.get('process_tree_rss_bytes') or 0)
    value['peak_tree_private_commit_bytes']=max(value['peak_tree_private_commit_bytes'],event.get('process_tree_private_bytes') or 0)
summary=dict(result=json.loads((directory/'result.json').read_text()),
    peak_tree_rss_gib=monitor['peak_rss_bytes']/GIB,
    peak_tree_private_commit_gib=monitor['peak_private_bytes']/GIB,
    host_available_start_gib=monitor['host_available_start_bytes']/GIB,
    host_available_minimum_gib=monitor['host_available_minimum_bytes']/GIB,
    maximum_forecast_gib=max(p['peak_bytes'] for p in plans)/GIB,
    peak_forecast_components=max(plans,key=lambda p:p['peak_bytes']),
    largest_inverse_ceiling_gib=max(p['inverse_ceiling_bytes'] for p in plans)/GIB,
    largest_measured_inverse_gib=max(e['actual_inverse_bytes'] for e in factors)/GIB,
    automatic_storage_first_gib=storage[0]['storage_bytes']/GIB,
    automatic_storage_minimum_gib=min(e['storage_bytes'] for e in storage)/GIB,
    automatic_storage_maximum_gib=max(e['storage_bytes'] for e in storage)/GIB,
    storage_read_count=len(storage), factor_build_count=len(factors),
    factor_events=factors, sampled_stage_peaks=stages,
    limitations=['Stage events use periodically sampled tree metrics, so phase boundaries are approximate.',
                'Live host availability also responds to unrelated applications.',
                'This run had ample headroom and does not validate behavior at 90% utilization.'])
(HERE/'live_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('factor_events','sampled_stage_peaks')},indent=2))
print('Factors:')
for e in factors:
    print('at',round(e['seconds'],2),'s: operator/inverse/allowance GiB:',
          *(round(e[k]/GIB,4) for k in ('operator_bytes','actual_inverse_bytes','inverse_budget_bytes')))
