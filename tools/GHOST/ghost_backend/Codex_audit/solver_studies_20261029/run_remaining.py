"""Run the remaining experiments serially to preserve timing comparability."""
import json
import subprocess
import sys
import time
from study import HERE,ROOT,run,save


if __name__=='__main__':
    if '--wait-capacity' in sys.argv:
        deadline=time.monotonic()+1800
        while not (HERE/'runs/capacity_dogleg_15ghz/monitor.json').exists():
            if time.monotonic()>deadline:raise RuntimeError('Capacity stage did not finish within the coordinator wait.')
            time.sleep(2)
    for plan_name in ('validation_plan.json','comparison_plan.json','research_plan.json'):
        for case in json.loads((HERE/plan_name).read_text()):
            run(case)
    tests=['tests/test_2d_capability_acceptance.py','tests/test_2d_resonance_2026_10_16.py',
        'tests/test_adaptive_polynomial.py','tests/test_large_geometry_followups.py',
        'tests/test_solver_resource_recovery.py','tests/test_tile_processes.py','tests/test_worker_moment_cache.py']
    process=subprocess.run([sys.executable,str(HERE/'validate.py'),*tests],cwd=ROOT)
    save(HERE/'suite_exit.json',dict(regression_exit_code=process.returncode))
    subprocess.run([sys.executable,str(HERE/'summarize.py')],cwd=ROOT,check=True)
