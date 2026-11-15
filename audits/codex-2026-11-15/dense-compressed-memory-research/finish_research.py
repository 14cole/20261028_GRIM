"""Run only after continue_research.py has completed; serial fresh processes."""
import os,sys,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
for args in [('check_layout.py',),('run_suite.py','suite_geometry_capture.json'),('run_suite.py','suite_sweeps.json'),('run_suite.py','suite_layout.json'),('residual_layout_benchmark.py',),('residual_output_benchmark.py',),('run_suite.py','suite_lifecycle.json'),('run_suite.py','suite_output.json'),('run_suite.py','suite_output_repeats.json'),('analyze.py',),('verify_sources.py',)]:
    print('PHASE',args,flush=True)
    subprocess.run([sys.executable,str(HERE/args[0]),*args[1:]],env=env,check=True)
