"""Strict comparison of the two golden.py archives; differences fail the run."""
import argparse
import json
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser()
parser.add_argument('baseline');parser.add_argument('cleaned')
args=parser.parse_args()
rows=[]
with np.load(args.baseline,allow_pickle=False) as a,np.load(args.cleaned,allow_pickle=False) as b:
    assert set(a.files)==set(b.files),'Fieldset keys differ'
    for key in a.files:
        left,right=a[key],b[key]
        assert left.shape==right.shape,key
        assert np.all(np.isfinite(left)) and np.all(np.isfinite(right)),key
        equal=left.dtype==right.dtype and left.tobytes()==right.tobytes()
        difference=float(np.max(abs(left-right)))
        rows.append(dict(case=key,shape=list(left.shape),bitwise_equal=equal,max_absolute_difference=difference))
        print(('PASS' if equal else 'FAIL'),key,difference)
Path(__file__).with_name('field-comparison.json').write_text(json.dumps(dict(fieldsets=len(rows),all_bitwise_equal=all(r['bitwise_equal'] for r in rows),cases=rows),indent=2))
assert all(r['bitwise_equal'] for r in rows),'Numerical fields changed'
