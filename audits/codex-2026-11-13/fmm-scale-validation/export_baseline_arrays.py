"""Optional compact publication export of the initial full-row evidence.
Usage: python export_baseline_arrays.py original.npz compact.npz metadata.json
Runtime/RSS JSON is never changed. Preserve the input in a separate path.
"""
import sys,json,hashlib
from pathlib import Path
import numpy as np
source,target,metadata=map(Path,sys.argv[1:]);assert source.resolve()!=target.resolve()
raw=source.read_bytes();data=dict(np.load(source));coeff=data.pop('exact_rows')
data['exact_row_residual']=coeff@data['density']-data['rhs'][data['rows']]
data['exact_row_norm']=np.sum(abs(coeff),axis=1)
np.savez_compressed(target,**data)
metadata.write_text(json.dumps(dict(original_npz_sha256=hashlib.sha256(raw).hexdigest(),published_npz_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),original_bytes=len(raw),published_bytes=target.stat().st_size,omitted='Regenerable exact_rows coefficient matrix; full solved arrays unchanged',coefficient_shape=list(coeff.shape),replacement='exact_row_residual and exact_row_norm computed from original exact_rows'),indent=2))
