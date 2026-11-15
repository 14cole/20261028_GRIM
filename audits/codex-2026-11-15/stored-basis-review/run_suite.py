"""Serial fresh-process measurements; retain every completed or failed run."""
import json,os,sys,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
results=HERE/'results';results.mkdir(exist_ok=True)
for label,spec in json.loads((HERE/(sys.argv[1] if len(sys.argv)>1 else 'suite.json')).read_text()):
    p=results/label
    if Path(str(p)+'.time.json').exists():raise RuntimeError('Existing case '+label)
    spec=dict(spec,out=str(p));started=time.perf_counter()
    print('START',label,flush=True)
    with Path(str(p)+'.stdout').open('w') as out,Path(str(p)+'.stderr').open('w') as err:
        r=subprocess.run([sys.executable,str(HERE/'run_case.py'),json.dumps(spec)],env=env,stdout=out,stderr=err)
    Path(str(p)+'.time.json').write_text(json.dumps(dict(returncode=r.returncode,wall_seconds=time.perf_counter()-started))+'\n')
    print('END',label,r.returncode,flush=True)
    if r.returncode:raise RuntimeError('Failed '+label)
