"""run_suite.py variant: cases with "right": true use monostatic_right.py."""
import json,os,sys,subprocess
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
root=Path(__file__).resolve().parent;os.chdir(root)
results_dir=Path(os.environ['MONOSTATIC_RESULTS']).resolve();results_dir.mkdir(parents=True,exist_ok=True)
for label,spec in json.loads(Path(sys.argv[1]).read_text()):
    spec=dict(spec,out=str(results_dir/label));script='monostatic_right.py' if spec.pop('right',False) else 'monostatic.py'
    if Path(spec['out']+'.time.json').exists():print('EXISTING',label,flush=True);continue
    print('START',label,flush=True)
    rc=subprocess.run([sys.executable,'measure.py',spec['out'],'--',sys.executable,script,json.dumps(spec)]).returncode
    print('END',label,rc,flush=True)
