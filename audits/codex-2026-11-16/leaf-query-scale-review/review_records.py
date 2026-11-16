"""Recompute report quantities from pinned Claude records; no solve replay."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;C=ROOT/'claude/results';out={}
for name in ('production','corrected-seq-direct-priced'):
    stem='k-star32768-'+name+'-audit'
    d=json.loads((C/(stem+'.json')).read_text());h=json.loads((C/(stem+'.hooks.json')).read_text())
    a=h['accounting'];leaf=h['audit'][0]['by_label']['leaf coefficients'];q=leaf['max_declared_additional']/2
    out[name]=dict(operator_bytes=d['stages']['assembly']['operator_bytes'],inverse_bytes=d['retained_factor_bytes'],
        inverse_high_water_bytes=a['high_water_with_check_bytes'],combined_high_water_mib=(d['stages']['assembly']['operator_bytes']+a['high_water_with_check_bytes'])/2**20,
        max_query_growth_bytes=leaf['max_growth_bytes'],max_query_growth_over_q=leaf['max_growth_bytes']/q,
        declared_bytes=leaf['max_declared_additional'],priced_bytes=4*q+2**20,
        peak_gib=d['peak_gib'],builds=h['builds'],condition_calls=[x for x in h['inverse_calls'] if x['phase']=='condition_probe'],
        exact_row_error=d['batches'][0]['max_exact_row_backward_error'],max_stored_rank=d['event']['compressed']['max_rank'],
        configured_leaf=d['event']['compressed']['leaf'])
out['retained_high_water_reduction_mib']=(out['production']['inverse_high_water_bytes']-out['corrected-seq-direct-priced']['inverse_high_water_bytes'])/2**20
out['peak_process_difference_gib']=out['production']['peak_gib']-out['corrected-seq-direct-priced']['peak_gib']
d=json.loads((C/'k-audit-multilayer-TM-corrected-seq-direct-priced.json').read_text())
leaf=d['hooks']['audit'][0]['by_label']['leaf coefficients'];q=leaf['max_declared_additional']/2
out['multilayer']=dict(query_growth_bytes=leaf['max_growth_bytes'],max_result_bytes=q,growth_over_q=leaf['max_growth_bytes']/q,
    note='Report says 1.7q; that divides by the 2q declaration. Result-byte ratio is about 3.43q.')
out['source_review']=dict(claude_commit='61290c9f213f974436727b0e75be1f60a7444fd2',
    published_star_field_arrays=False,published_star_density_arrays=False,
    array_replay_possible=False,scope='The full pinned Git tree contains only two multilayer field NPZ files under this review path.')
(ROOT/'claude-record-analysis.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
