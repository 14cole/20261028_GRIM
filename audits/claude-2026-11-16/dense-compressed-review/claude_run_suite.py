"""Reviewer suite runner: like run_suite.py, plus kernel-reported child peak RSS."""
import os,sys,json,subprocess,time,resource
from pathlib import Path
HERE=Path(__file__).resolve().parent
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
(HERE/'results').mkdir(exist_ok=True)
for label,spec in json.loads((HERE/sys.argv[1]).read_text()):
    out=HERE/'results'/label
    if Path(str(out)+'.time.json').exists():print('EXISTING',label,flush=True);continue
    spec=dict(spec,out=str(out));print('START',label,flush=True)
    code="import resource,subprocess,sys,json,time;t=time.perf_counter();p=subprocess.run(sys.argv[2:]);print(json.dumps(dict(returncode=p.returncode,wall_seconds=time.perf_counter()-t,child_peak_gib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss/2**20)),file=open(sys.argv[1],'w'))"
    with Path(str(out)+'.stdout').open('w') as o,Path(str(out)+'.stderr').open('w') as e:
        p=subprocess.run([sys.executable,'-c',code,str(out)+'.time.json',sys.executable,str(HERE/spec.get('runner','run_star.py')),json.dumps(spec)],env=env,stdout=o,stderr=e)
    print('END',label,Path(str(out)+'.time.json').read_text().strip(),flush=True)
