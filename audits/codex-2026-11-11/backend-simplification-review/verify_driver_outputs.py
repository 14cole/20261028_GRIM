"""Fail on missing/different arrays or unexpected HPC restart/tamper outcomes."""
import json
from pathlib import Path
import sys
import numpy as np

root = Path(sys.argv[1])
rows = []
for kind in ('local-twod', 'hpc-twod', 'local-bor', 'hpc-bor'):
    for certified in (0, 1):
        spec = f'{kind}-{certified}'
        dirs = [root / 'drvout' / f'{side}-{spec}' for side in ('base', 'new')]
        events = [json.loads((p / 'events.json').read_text()) for p in dirs]
        expected_artifacts = 10 if kind.endswith('bor') else 4
        with np.load(dirs[0] / 'arrays.npz') as a, np.load(dirs[1] / 'arrays.npz') as b:
            assert set(a.files) == set(b.files), spec
            for key in a.files:
                assert a[key].shape == b[key].shape and a[key].dtype == b[key].dtype, (spec, key)
                assert a[key].tobytes() == b[key].tobytes(), (spec, key)
            count = len(a.files)
        assert events[0]['artifacts'] == events[1]['artifacts'], spec
        assert len(events[0]['artifacts']) == expected_artifacts, spec
        for event in events:
            assert event['submit_rc'] == 0, (spec, event)
            if kind.startswith('hpc'):
                assert event['worker_rc'] == event['resume_rc'] == event['partial_rc'] == 0
                assert event['resume_rewrote'] == event['partial_rewrote_others'] == []
                assert event['partial_restored_victim'] is True
                assert event['partial_arrays_equal'] is True
                assert event['tamper_rc'] == 1 and event['tamper_restored_victim'] is False
                assert event['tamper_artifact_count'] == expected_artifacts - 1
                assert 'changed' in event['tamper_message'] or 'mismatch' in event['tamper_message']
        assert events[0]['frozen_runtime_files'] == 209
        assert events[1]['frozen_runtime_files'] == 214
        rows.append(dict(case=spec, artifacts=expected_artifacts, arrays=count,
                         bitwise_equal=True, baseline_events=events[0], new_events=events[1]))
summary = dict(pairs=len(rows), numeric_arrays_compared=sum(r['arrays'] for r in rows),
               all_bitwise_equal=True, all_restart_assertions_passed=True, cases=rows)
(root / 'verified-driver-results.json').write_text(json.dumps(summary, indent=2)+'\n')
print('PASS:', summary['pairs'], 'driver pairs;', summary['numeric_arrays_compared'],
      'bitwise-identical arrays; all restart/tamper assertions passed')
