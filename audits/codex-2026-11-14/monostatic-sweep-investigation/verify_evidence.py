"""Internal archive roundtrip check; requires original batch NPZs in results/.

The published archive consolidates batches. Reviewers can verify every restored
array hash with unpack_arrays.py; this additional check was run locally against
the original pre-archive batches and its result is evidence-verification.json.
"""
import json,hashlib,os
from pathlib import Path
import numpy as np
from evidence_paths import batches
from unpack_arrays import restore
ROOT=Path(__file__).resolve().parent
count=restore(ROOT/'publication',ROOT/'restored')
manifest=json.loads((ROOT/'publication/ARRAYS_MANIFEST.json').read_text())
checked=0
for label in manifest['cases']:
    paths=batches(ROOT/'results',label)
    blocks=[]
    for path in paths:
        with np.load(path,allow_pickle=False) as z:blocks.append({k:z[k] for k in z.files})
    with np.load(ROOT/'restored/results'/(label+'.npz'),allow_pickle=False) as z:
        assert set(z.files)==set(blocks[0]),label
        for key in z.files:
            expected=blocks[0][key] if key in ('rows','row_norm') else np.concatenate([b[key] for b in blocks],axis=1 if key in ('density','rhs','residual') else 0)
            actual=z[key]
            assert actual.dtype==expected.dtype and actual.shape==expected.shape and actual.tobytes()==expected.tobytes(),(label,key)
            checked+=1
env=json.loads((ROOT/'environment.json').read_text())
production=Path(os.environ['GRIM_ROOT'])/'tools/GHOST'
for name,expected in env['production_hashes'].items():
    assert hashlib.sha256((production/name).read_bytes()).hexdigest()==expected,name
result=dict(cases=count,arrays_bitwise_verified=checked,production_files_unchanged=len(env['production_hashes']),archive_sha256=manifest['archive_sha256'])
(ROOT/'evidence-verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
