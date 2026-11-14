"""Serial fresh-process measurements. No competing benchmarks; failures retained."""
import json,os,sys,subprocess
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.environ.setdefault('GRIM_ROOT','/workspace/fmm-scale-study/candidate')
root=Path(__file__).resolve().parent;os.chdir(root)
results_dir=Path(os.environ.get('MONOSTATIC_RESULTS','results')).resolve()
results_dir.mkdir(parents=True,exist_ok=True)
manifest=json.loads(Path(sys.argv[1]).read_text())
if Path(sys.argv[1]).name=='suite2.json':
    os.environ['MONOSTATIC_RESULTS']=str(results_dir)
    os.environ.setdefault('MONOSTATIC_ANALYSIS',str(results_dir/'preflight-analysis.json'))
    for script,out in [('check_batched.py','batched-check.json'),('check_projection.py','projection-check.json'),('analyze.py','preflight-analysis.stdout')]:
        with open(results_dir/('_'+out),'w') as f:
            subprocess.run([sys.executable,script],stdout=f,stderr=subprocess.STDOUT,check=True)
for label,spec in manifest:
    spec=dict(spec,out=str(results_dir/label))
    if Path(spec['out']+'.time.json').exists():
        print('EXISTING',label,flush=True);continue
    print('START',label,flush=True)
    rc=subprocess.run([sys.executable,'measure.py',spec['out'],'--',sys.executable,'monostatic.py',json.dumps(spec)]).returncode
    print('END',label,rc,flush=True)
