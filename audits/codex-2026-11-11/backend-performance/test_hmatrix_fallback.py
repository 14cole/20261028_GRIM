"""Force H-matrix on modest native-free PEC/dielectric solves and compare fields."""
import json, os, subprocess, sys
from pathlib import Path
import numpy as np
here = Path(__file__).resolve().parent
roots = dict(zip(('base-fallback', 'new-fallback', 'new-native'), sys.argv[1:]))
assert len(roots) == 3, 'Provide BASE_NATIVE_FREE NEW_NATIVE_FREE NEW_NATIVE'
for name in ('base-fallback', 'new-fallback'):
    assert not any(p.suffix.lower() in ('.so', '.dll') for p in Path(roots[name]).rglob('*'))
out = here / 'hmatrix-fallback'; out.mkdir(exist_ok=True)
rows = []; fields = {}
for body, n in (('pec', 1200), ('diel', 600)):
    for side, root in roots.items():
        tag = body + '-' + side
        spec = dict(body=body, n=n, angles=19, backend='compressed',
                    options=dict(assembly_threads=1, blas_threads='auto'),
                    env=dict(GHOST_HMATRIX_MIN_UNKNOWNS=1024))
        p = subprocess.run([sys.executable, str(here/'case.py'), root, json.dumps(spec)],
                           capture_output=True, text=True, timeout=600,
                           env=dict(os.environ, REVIEW_RESULT_PATH=str(out/tag)))
        assert p.returncode == 0, p.stderr
        r = json.loads(p.stdout.splitlines()[-1])
        assert not r['error'] and r['linear_backend'] == 'cpu_hmatrix', r
        samples = json.loads((out/(tag+'.samples.json')).read_text())
        meta = json.loads((out/(tag+'.metadata.json')).read_text())
        assert meta['quality_gate']['passed']
        fields[tag] = np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in samples])
        assert len(fields[tag]) == 38 and np.all(np.isfinite(fields[tag]))
    for side in ('base-fallback', 'new-native'):
        a, b = fields[body+'-'+side], fields[body+'-new-fallback']
        error = float(np.max(abs(a-b))/max(np.max(abs(a)), 1e-300))
        assert error < 1e-9, (body, side, error)
        rows.append(dict(body=body, reference=side, norm_scaled_error=error,
                         bitwise_equal=a.tobytes()==b.tobytes(), samples=len(a)))
np.savez_compressed(here/'hmatrix-fallback-fields.npz', **fields)
(here/'hmatrix-fallback-results.json').write_text(json.dumps(rows, indent=2)+'\n')
print('PASS six H-matrix solves, four native-free/native comparisons', flush=True)
