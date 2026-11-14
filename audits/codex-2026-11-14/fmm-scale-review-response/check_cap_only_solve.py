"""Check cap-only integration on actual saved 2,048-unknown solutions."""
import json,sys
from pathlib import Path
from compare_policy_fields import compare_fields
root=Path(sys.argv[1] if len(sys.argv)>1 else 'results')
names=['sampling-baseline-2048','forecast-only-cap-8-2048'];b,c=[json.loads((root/(n+'.json')).read_text()) for n in names]
assert all(json.loads((root/(n+'.time.json')).read_text())['rc']==0 for n in names)
s=c['adaptive_sketch_evidence'];assert not s['enabled'] and s['capped_calls']>0 and s['reduced_selections']==0
metrics=compare_fields(root/(names[0]+'.npz'),root/(names[1]+'.npz'))
result=dict(unknowns=2048,experiment='Correctness smoke test, not a speed benchmark',cap=s,baseline_max_rank=b['operator_evidence']['max_rank'],cap_only_max_rank=c['operator_evidence']['max_rank'],**metrics,baseline_sampled_backward_error=b['event']['max_sampled_backward_error'],cap_only_sampled_backward_error=c['event']['max_sampled_backward_error'])
assert result['cap_only_max_rank']>8
(root/'cap-only-solve-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
