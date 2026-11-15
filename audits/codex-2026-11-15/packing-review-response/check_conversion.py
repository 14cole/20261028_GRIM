import json
from pathlib import Path
import numpy as np
from hooks import convert
cases={
    'tiny_among_normal': np.array([1.+2j,9.1e-46+1e-50j]),
    'all_tiny': np.array([9.1e-46+1e-50j]),
    'overflow': np.array([1e39+1j]),
    'zeros': np.zeros(3,complex),
    'small_component': np.array([1.+1e-50j]),
    'normal': np.random.default_rng(41).normal(size=(19,12)).astype(complex),
}
records={}
for name,a in cases.items():
    result,record=convert(a)
    accepted=name not in ('all_tiny','overflow')
    assert record['accepted']==accepted
    assert result.dtype==(np.complex64 if accepted else np.complex128)
    if not accepted:assert result is a
    records[name]=dict(record)
    if not np.isfinite(records[name]['relative_max_component_error']):
        records[name]['relative_max_component_error']=None
for value in (np.nan,np.inf):
    try:convert(np.array([value],complex))
    except FloatingPointError:pass
    else:raise AssertionError('Nonfinite input accepted')
Path(__file__).with_name('conversion-check.json').write_text(json.dumps(records,indent=2,allow_nan=False))
print('Conversion checks passed, including double fallback and nonfinite rejection')
