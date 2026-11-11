"""Strict before/after comparison for both reference execution paths."""
import json
from pathlib import Path
import sys
import numpy as np

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
rows = []
for mode in ('native', 'fallback'):
    with np.load(root / ('base-' + mode + '.npz')) as a, np.load(root / ('new-' + mode + '.npz')) as b:
        assert set(a.files) == set(b.files) and len(a.files) == 31
        for key in a.files:
            assert a[key].dtype == b[key].dtype and a[key].shape == b[key].shape
            assert np.all(np.isfinite(a[key])) and np.all(np.isfinite(b[key]))
            assert a[key].tobytes() == b[key].tobytes(), (mode, key)
            rows.append(dict(mode=mode, case=key, bitwise_equal=True))
(root / 'field-comparison.json').write_text(json.dumps(dict(total=len(rows), cases=rows), indent=2) + '\n')
print('PASS: 62/62 result sets bitwise identical (31 native, 31 fallback)')
