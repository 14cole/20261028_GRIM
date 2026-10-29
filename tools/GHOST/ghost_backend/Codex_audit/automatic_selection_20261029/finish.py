"""Run integration checks after the final serial trial, avoiding timing contention."""
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
deadline=time.monotonic()+7200
while not (HERE/'runs/coated3_condition_diagnostic/monitor.json').exists():
    if time.monotonic()>deadline:raise RuntimeError('Trial completion deadline exceeded.')
    time.sleep(3)
tests=['test_selection_explanations','test_automatic_backend','test_nearby_timing_history',
       'test_stage_cost_model','test_adaptive_polynomial','test_batch_planning_reuse',
       'test_automatic_hpc','test_solver_resource_recovery']
process=subprocess.run([sys.executable,str(HERE/'validate.py'),
                        *['tests/'+name+'.py' for name in tests]],cwd=ROOT)
(HERE/'suite_exit.json').write_text(json.dumps(dict(exit_code=process.returncode)),encoding='utf-8')
raise SystemExit(process.returncode)
