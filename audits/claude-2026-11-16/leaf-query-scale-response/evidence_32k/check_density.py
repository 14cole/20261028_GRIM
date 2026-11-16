"""Check the published 32k density parts against the hashes of the two leaf-query-response 32k runs.
Usage (from the repository root, branch claude/festive-keller-nj5bje):
  python audits/claude-2026-11-16/leaf-query-scale-response/evidence_32k/check_density.py
The production run of 61290c9 was bit-identical to the earlier 32k Compressed run whose full
density is published in two parts under audits/claude-2026-11-15/stored-basis-response-review/arrays/.
"""
import json,hashlib
from pathlib import Path
import numpy as np
here=Path(__file__).resolve().parent;root=here.parents[3]
parts=[np.load(root/'audits/claude-2026-11-15/stored-basis-response-review/arrays'/f'c32k-compressed-180-density-part{i}.npz') for i in (0,1)]
density=np.concatenate([p['density'] for p in parts],axis=1);field=parts[0]['field']
digest=hashlib.sha256(np.ascontiguousarray(density).tobytes()).hexdigest()
idx=json.loads((here/'array_hashes.json').read_text());ok=True
for label,entry in idx.items():
    small=np.load(here/f'{label}-fields-and-rows.npz')
    checks=dict(density_hash=entry['density']['sha256_c_order']==digest,field_bitwise=bool(np.array_equal(small['field'],field)),
        field_hash=hashlib.sha256(np.ascontiguousarray(small['field']).tobytes()).hexdigest()==entry['field']['sha256_c_order'])
    print(label,checks);ok=ok and all(checks.values())
print('ALL OK' if ok else 'MISMATCH');raise SystemExit(0 if ok else 1)
