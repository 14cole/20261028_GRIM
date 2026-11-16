"""Compare fresh complete fields with pinned Claude JSON samples, not new solves."""
import json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;out=[]
for name,ref in [('cap690-production-0','j-cap690-multilayer-TM-production-none-0'),('cap690-sequential-1','j-cap690-multilayer-TM-corrected-seq-none-1')]:
    d=json.loads((P/'claude/results'/(ref+'.json')).read_text())
    b=np.array([complex(s['rcs_amp_real'],s['rcs_amp_imag']) for s in d['samples']])
    with np.load(P/'results'/(name+'-fields.npz')) as z:a=z['field']
    assert a.shape==b.shape
    error=float(np.max(abs(a-b))/np.max(abs(b)));assert error<1e-10
    out.append(dict(case=name,claude_case=ref,bit_identical=bool(a.dtype==b.dtype and a.tobytes()==b.tobytes()),peak_normalized_field_difference=error))
(P/'claude-field-comparison.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
