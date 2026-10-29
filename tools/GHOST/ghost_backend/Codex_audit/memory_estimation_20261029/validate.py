"""Run audit regressions with a saved, bounded failure report."""
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT.parent), str(ROOT / 'tests')]
os.environ.update(OPENBLAS_NUM_THREADS='4', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4',
                  PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', QT_QPA_PLATFORM='offscreen',
                  PYTHONIOENCODING='utf-8')
# Headless tests create and rename complete runtime directories. Keep those
# inside the writable workspace, and make child log encoding deterministic.
temporary = HERE / 'test_temp'
temporary.mkdir(exist_ok=True)
os.environ.update(TEMP=str(temporary), TMP=str(temporary))
os.chdir(ROOT)
import pytest


class Report:
    def __init__(self):
        self.rows = []
        self.path = HERE / ('validation_results_' + str(time.time_ns()) + '.json')

    def pytest_runtest_logreport(self, report):
        if report.when == 'call' or report.failed:
            row = dict(test=report.nodeid, phase=report.when, outcome=report.outcome, seconds=report.duration)
            if report.failed:
                row['failure'] = str(report.longrepr)
                print(row['failure'][-8000:], flush=True)
            self.rows.append(row)
            self.path.write_text(json.dumps(self.rows, indent=2), encoding='utf-8')
            (HERE / 'validation_results.json').write_text(json.dumps(self.rows, indent=2), encoding='utf-8')


if __name__ == '__main__':
    paths = sys.argv[1:] or ['tests/test_run_controls.py', 'tests/test_factorization_audit_resources.py',
        'tests/test_compressed_memory.py', 'tests/test_hmatrix_resource_bounds.py',
        'tests/test_bounded_factor_workspaces.py', 'tests/test_factor_crossover_scope.py',
        'tests/test_compressed_projection_storage.py', 'tests/test_automatic_backend.py']
    scratch = HERE / ('validation_tmp_' + str(time.time_ns()))
    assert scratch.parent == HERE and not scratch.exists()
    code = pytest.main([*paths, '-q', '--tb=short', '--rootdir=' + str(ROOT), '--basetemp=' + str(scratch),
                        '-p', 'no:cacheprovider', '-o', 'faulthandler_timeout=60'], plugins=[Report()])
    (HERE / 'validation_exit_code.txt').write_text(str(code))
    raise SystemExit(code)
