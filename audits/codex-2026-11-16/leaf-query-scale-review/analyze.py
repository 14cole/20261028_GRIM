"""Recheck complete fresh arrays against the preserved, previously published control."""
import os,json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
RESULTS=Path(os.environ.get('RESULTS_DIR',str(ROOT/'results')))
def digest(a):return hashlib.sha256(a.tobytes()).hexdigest()
def compare(a,b):
    assert a.shape==b.shape and a.dtype==b.dtype
    error=a-b
    if a.ndim==2:
        errs=[float(np.linalg.norm(error[:,j])/max(np.linalg.norm(b[:,j]),1e-300)) for j in range(a.shape[1])]
        relative=max(errs,default=0.)
    else:relative=float(np.linalg.norm(error)/max(np.linalg.norm(b),1e-300))
    return dict(shape=list(a.shape),dtype=a.dtype.str,bit_identical=a.tobytes()==b.tobytes(),
        max_column_relative_error=relative,peak_normalized_error=float(np.max(abs(error))/max(np.max(abs(b)),1e-300)),
        sha256=digest(a),reference_sha256=digest(b))
reference_path=RESULTS/'reference-uncapped-batch0000.npz'
cases=[]
with np.load(reference_path) as z:reference={k:z[k] for k in z.files}
for label,spec in json.loads((ROOT/'suite_capacity.json').read_text()):
    timing=json.loads((RESULTS/(label+'.time.json')).read_text());hooks=json.loads((RESULTS/(label+'.hooks.json')).read_text())
    d=dict(label=label,spec=spec,timing=timing,hooks=hooks)
    if timing['returncode']:
        failure=json.loads((RESULTS/(label+'.failure.json')).read_text())
        assert label=='cap2900-production' and 'MemoryError' in failure['traceback'],failure
        d['outcome']='retained-storage rejection';d['failure']=failure
    else:
        raw=json.loads((RESULTS/(label+'.json')).read_text());d['outcome']='accepted research solve'
        d['compute_seconds']=raw['compute_seconds'];d['stages']=raw['stages'];d['peak_gib']=raw['peak_gib']
        d['factor_bytes']=raw['retained_factor_bytes'];d['event']=raw['event']
        with np.load(RESULTS/(label+'-batch0000.npz')) as z:
            arrays={k:z[k] for k in z.files}
        for key in ('density','rhs','field','residual'):assert np.isfinite(arrays[key]).all()
        d['comparisons']={k:compare(arrays[k],reference[k]) for k in ('density','rhs','field')}
        assert d['comparisons']['rhs']['bit_identical']
        assert max(d['comparisons'][k]['max_column_relative_error'] for k in ('density','field'))<1e-8
        den=arrays['row_norm'][:,None]*np.max(abs(arrays['density']),axis=0)+abs(arrays['rhs'][arrays['rows']])
        backward=np.max(abs(arrays['residual'])/den,axis=0)
        assert len(backward)==180 and np.max(backward)<1e-12
        d['independent_exact_rows']=dict(count=len(arrays['rows']),angles=len(backward),max_backward_error=float(np.max(backward)))
        d['array_hashes']={k:dict(shape=list(a.shape),dtype=a.dtype.str,sha256=digest(a)) for k,a in arrays.items()}
        assert int(raw['event']['unknowns'])==32768
        assert not raw['production_certified'] and not raw['mesh_certified']
        if label=='cap2900-sequential':
            assert hooks['builds']==1 and hooks['accounting']['final_bytes']==[974777536]
            assert all(d['comparisons'][k]['bit_identical'] for k in ('density','rhs','field'))
        else:assert hooks['builds']>=2 and 'compact_preconditioner' in raw['event']
        del arrays
    cases.append(d)
assert cases[1]['outcome']=='accepted research solve'
report=dict(cases=cases,reference=json.loads((RESULTS/'reference-uncapped.json').read_text()),
    scope='One fresh untraced run per mode, 180 monostatic angles, shared assembly. No condition estimation or mesh certification.')
out=Path(os.environ.get('ANALYSIS_OUT',str(ROOT/'analysis.json')));out.write_text(json.dumps(report,indent=2))
print(json.dumps([{k:d[k] for k in ('label','outcome','timing')} for d in cases],indent=2))
