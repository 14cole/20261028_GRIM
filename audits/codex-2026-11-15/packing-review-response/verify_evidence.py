"""Compare reconstructed evidence with every original array and record bit."""
import json,sys,hashlib
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
original=HERE/'results';restored=Path(sys.argv[1])/'results';arrays=0;values=0;records=0
assert {p.name for p in original.iterdir() if p.is_file()}=={p.name for p in restored.iterdir() if p.is_file()}
for p in sorted(original.iterdir()):
    if not p.is_file():continue
    q=restored/p.name
    if p.suffix=='.npz':
        with np.load(p) as a,np.load(q) as b:
            assert a.files==b.files or set(a.files)==set(b.files)
            for key in a.files:
                x,y=a[key],b[key]
                assert x.dtype==y.dtype and x.shape==y.shape
                assert x.tobytes()==y.tobytes(),(p.name,key)
                assert x.flags.c_contiguous==y.flags.c_contiguous and x.flags.f_contiguous==y.flags.f_contiguous
                arrays+=1;values+=x.size
    else:
        assert p.read_bytes()==q.read_bytes(),p.name;records+=1
d=dict(array_count=arrays,array_values=values,records=records,all_bits_and_layouts_match=True)
(HERE/'evidence-verification.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))
