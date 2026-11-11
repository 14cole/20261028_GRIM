"""Exercise GRIM's discovery, diagnostics and embedded GHOST workspace.

Run in a disposable checkout; two negative tests briefly rename files, with
restoration in finally blocks. Never run concurrently against that checkout.
"""
import argparse
import json
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('checkout')
args = parser.parse_args()
root = Path(args.checkout).resolve()
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ.pop('GHOST_BACKEND_PATH', None)
sys.path.insert(0, str(root))
from GRIM_Backend.execution import diagnostics as D
from GRIM_Backend.integrations import ghost as G

checks = []
def check(name, condition):
    assert condition, name
    checks.append(name)
    print('PASS', name, flush=True)

backend = root / 'tools/GHOST/ghost_backend'
check('bundled backend discovery', G.discover_ghost_backend() == backend)
check('explicit backend discovery', G.discover_ghost_backend(backend) == backend)
check('explicit invalid override fails closed',
      G.discover_ghost_backend(root / 'missing-backend') is None)
for name in ('assembly_inspector', 'grim_io', 'line_expand'):
    module = G.load_ghost_module(name)
    check(name + ' loads from selected backend',
          Path(module.__file__).resolve().is_relative_to(backend))

results = D.collect_diagnostics(root)
check('all required GRIM diagnostics pass',
      all(r.status == 'PASS' for r in results if r.required))
check('GRIM startup diagnostic exit is zero', D.startup_exit_code(results) == 0)
check('current bundled BLAS controls pass',
      D._bundled_thread_control_result(backend).status == 'PASS')

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
widget = G.GhostIntegrationWidget()
check('GRIM embedded GHOST workspace constructs', widget.workspace is not None)
check('embedded Geometry tab available', widget.workspace.geometry_tab is not None)
check('embedded Solver tab available', widget.workspace.solver_tab is not None)
widget.close()
widget.deleteLater()
app.processEvents()

current = backend / 'execution/thread_control/_threadpoolctl.py'
saved = current.with_suffix('.py.bc01-test-backup')
assert not saved.exists()
current.rename(saved)
try:
    check('missing active backend file still rejects discovery',
          G.discover_ghost_backend() is None)
finally:
    saved.rename(current)

license_path = backend / 'execution/thread_control/LICENSE-3.6.0.txt'
saved = license_path.with_suffix('.txt.bc01-test-backup')
assert not saved.exists()
license_path.rename(saved)
try:
    check('missing active license still fails diagnostic',
          D._bundled_thread_control_result(backend).status == 'FAIL')
finally:
    saved.rename(license_path)
check('discovery restored after negative tests', G.discover_ghost_backend() == backend)
check('thread-control diagnostic restored after negative tests',
      D._bundled_thread_control_result(backend).status == 'PASS')
Path(__file__).with_name('integration-regression-results.json').write_text(
    json.dumps(dict(passed=len(checks), checks=checks), indent=2) + '\n')
