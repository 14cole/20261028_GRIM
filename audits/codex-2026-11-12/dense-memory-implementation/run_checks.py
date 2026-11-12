"""Run safety/workflow regressions against a selected repository checkout."""
import os,subprocess,sys
from pathlib import Path
p=Path(__file__).resolve().parent;root=Path(sys.argv[1]).resolve()
(p/'results').mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith('GHOST_')}
env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
for name in ('test_plans','test_residual_safety','test_bounded_spool','test_workflows','test_alternate_paths','test_cap_resolution'):
 done=subprocess.run([sys.executable,str(p/(name+'.py')),str(root),str(p/'results')],env=env,capture_output=True,text=True,timeout=300)
 (p/'results'/(name+'.log')).write_text(done.stdout+done.stderr)
 print(name,done.returncode,flush=True)
 if done.returncode:raise RuntimeError(done.stdout+done.stderr)
