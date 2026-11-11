"""Recheck every archived benchmark field, not only printed sample angles."""
import json
from pathlib import Path
import numpy as np

here = Path(__file__).resolve().parent
results = []
for suite in ('blas-results', 'default-results'):
    path = here / suite
    rows = [json.loads(line) for line in (path / 'timings.jsonl').read_text().splitlines()]
    failures = {r['tag'] for r in rows if r.get('error')}
    assert failures == (set() if suite == 'blas-results' else
                        {'coated6480-base-r1', 'pec8k-base-r1'})
    assert all(r['returncode'] == 0 for r in rows)
    metadata = json.loads((path / 'metadata-summary.json').read_text())
    assert all(r['quality_passed'] for r in metadata)
    assert {r['case'] for r in metadata} == {r['tag'] for r in rows} - failures
    with np.load(path / 'fields.npz', allow_pickle=False) as fields:
        for row in rows:
            tag = row['tag']
            if '-new-' not in tag:
                continue
            base = tag.replace('-new-', '-base-')
            if base in failures:
                continue
            a, b = fields[base], fields[tag]
            assert a.shape == b.shape == (362, 6)
            assert np.array_equal(a[:, :3], b[:, :3])
            assert np.array_equal(fields[base + '__polarization'], fields[tag + '__polarization'])
            assert np.all(np.isfinite(a)) and np.all(np.isfinite(b))
            x, y = a[:, 3] + 1j*a[:, 4], b[:, 3] + 1j*b[:, 4]
            relative = float(np.max(abs(x-y)) / max(np.max(abs(x)), 1e-300))
            assert relative < 1e-8, (suite, tag, relative)
            results.append(dict(suite=suite, case=tag, samples=len(x),
                                norm_scaled_max_error=relative,
                                max_db_difference=float(np.max(abs(a[:, 5]-b[:, 5])))))
with np.load(here / 'default-results/fields.npz') as fields, np.load(here / 'recovered-references.npz') as ref:
    for tag in ('coated6480', 'pec8k'):
        actual = fields[tag + '-new-r1']
        assert actual.tobytes() == ref[tag].tobytes(), tag
        assert np.array_equal(fields[tag + '-new-r1__polarization'], ref[tag + '__polarization'])
(here / 'benchmark-field-verification.json').write_text(json.dumps(results, indent=2) + '\n')
print('PASS', len(results), 'benchmark field pairs and 2 recovered-case dense references')
