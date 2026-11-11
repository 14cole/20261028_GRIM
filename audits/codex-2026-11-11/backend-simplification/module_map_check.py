"""Gate GRIM discovery and all mapped imports, including new-file absence checks."""
import json
import os
from pathlib import Path
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ.pop('GHOST_BACKEND_PATH', None)
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from GRIM_Backend.integrations import ghost as G
from GRIM_Backend.execution import diagnostics as D

backend = root / 'tools/GHOST/ghost_backend'
assert G.discover_ghost_backend() == backend
assert len(D.GHOST_MODULE_LOCATIONS) == 68
for name in D.GHOST_MODULE_LOCATIONS:
    G.load_ghost_module(name)
assert len(D.GHOST_SENTINELS) == 126
for name in ('runs/driver_settings.py', 'runs/worker_pipeline.py',
             'bor/constraints.py', 'bor/validation.py', 'bor/storage.py'):
    path = backend / name
    saved = path.with_suffix('.py.check-backup')
    assert not saved.exists()
    path.rename(saved)
    try:
        assert G.discover_ghost_backend() is None, name
    finally:
        saved.rename(path)
assert G.discover_ghost_backend() == backend
assert D.startup_exit_code(D.collect_diagnostics(root)) == 0
print(json.dumps(dict(mapped_modules_loaded=68, required_files_present=126,
                      new_module_absence_rejected=5, diagnostics_exit=0)))
