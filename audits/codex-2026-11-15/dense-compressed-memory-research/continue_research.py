import subprocess,sys,os
from pathlib import Path
HERE=Path(__file__).resolve().parent
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
for args in [('run_suite.py','suite_adjoint.json'),('run_suite.py','suite_geometry.json'),('residual_benchmark.py',),('run_suite.py','suite_scale.json')]:
    print('PHASE',args,flush=True)
    subprocess.run([sys.executable,str(HERE/args[0]),*args[1:]],env=env,check=True)
