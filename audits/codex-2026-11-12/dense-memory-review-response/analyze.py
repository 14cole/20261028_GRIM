"""Compare complete fields and summarize the independent review checks."""
import json
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;r=p/'results'
def compare(a,b):
 a=np.load(a)['field'];b=np.load(b)['field'];assert a.shape==b.shape and np.isfinite(a).all()
 return dict(samples=len(a),bitwise_equal=bool(np.array_equal(a,b)),relative_field_difference=float(np.max(abs(a-b))/np.max(abs(b))),max_rcs_db_difference=float(np.max(abs(20*np.log10(abs(a)/abs(b))))))
rows=dict(airfoil=compare(r/'airfoil-reference-1g.npz',r/'airfoil-reference.npz'),
 dielectric_same_four_cpus=compare(r/'diel-disk-2.4g.npz',r/'diel-memory-4g.npz'))
if (p/'references/diel8-default-0.npz').exists():
 rows['dielectric_historical_five_cpus']=compare(r/'diel-disk-2.4g.npz',p/'references/diel8-default-0.npz')
assert rows['airfoil']['relative_field_difference']<1e-11
assert rows['dielectric_same_four_cpus']['bitwise_equal']
rows['policy_examples']=len(json.loads((r/'policy.json').read_text()))
rows['reviewed_runtime']='ae08d66dc309c393ce62cc76bacd510a150ebf33'
(p/'VALIDATION_SUMMARY.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
