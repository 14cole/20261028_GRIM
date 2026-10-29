"""Run the union of both affected regression sets after profiling is complete."""
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
deadline=time.monotonic()+900
while not (HERE/'runs/profile_narrow_8/monitor.json').exists():
    if time.monotonic()>deadline:raise RuntimeError('Worker profiling did not finish')
    time.sleep(1)
assert json.loads((HERE/'runs/profile_narrow_8/monitor.json').read_text())['returncode']==0
files={'tests/test_commit_capacity_growth.py','tests/test_idle_worker_transition.py'}
for previous in ('memory_implementation_20261029','memory_followups_20261029'):
    files.update(json.loads((HERE.parent/previous/'validation_summary.json').read_text())['test_files'])
(HERE/'combined_test_files.json').write_text(json.dumps(sorted(files),indent=2)+'\n')
subprocess.run([sys.executable,str(HERE/'validate.py'),*sorted(files)],check=True)
