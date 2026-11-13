"""Recompute the review response from full fields and independent coefficient rows."""
from pathlib import Path
import json,numpy as np
root=Path('.')
metric=json.loads((root/'metric-rerun.json').read_text());claude=json.loads((root/'claude/results/claude_stadium_metric.json').read_text())
keys=['K_max_entry','K_abs_error_max','K_error_over_K_max','combined_block_error_max_over_max']
assert all(metric[case][key]==claude[case][key] for case in metric for key in keys)
policies=json.loads((root/'scale-policy.json').read_text())
assert all(r['ranks'][1]==2 for r in policies if r['policy']=='largest_partner' and r['mode']=='common_amplitude')
assert [r['ranks'][1] for r in policies if r['policy']=='largest_partner' and r['mode']=='length_units']==[0,2,0]
dense=np.load('results/matched-dense.npz');comparisons=[]
for kind in ['compressed','fmm']:
 z=np.load('results/matched-'+kind+'.npz');row={'method':kind}
 for key in ['field','density']:
  row[key+'_relative_max_error']=float(np.max(abs(z[key]-dense[key]))/np.max(abs(dense[key])))
 assert row['field_relative_max_error']<1e-9
 comparisons.append(row)
fmm=np.load('results/matched-fmm.npz');b=fmm['rhs'];x=fmm['density'];rows=fmm['rows'];exact=fmm['exact_rows']
r=exact@x-b[rows];error=np.max(abs(r)/(np.sum(abs(exact),axis=1)[:,None]*np.max(abs(x),axis=0)+abs(b[rows])),axis=0)
assert np.max(error)<1e-12
records={kind:json.loads(Path('results/matched-'+kind+'.time.json').read_text()) for kind in ['dense','compressed','fmm']}
for kind in records:
 assert records[kind]['rc']==0
 events=json.loads(Path('results/matched-'+kind+'-kernels.json').read_text());assert any(x['used'] for x in events)
assert records['fmm']['spec']['op_tol']==records['fmm']['spec']['inv_tol']==.01
c=records['compressed'];f=records['fmm']
print(json.dumps(dict(metric_maxima_match_exactly=True,scale_counterexample_verified=True,comparisons=comparisons,exact_row_backward_errors=error.tolist(),external_timings=records,fmm_time_ratio=f['wall_s']/c['wall_s'],fmm_peak_saving=1-f['peak_gib']/c['peak_gib']),indent=2))
