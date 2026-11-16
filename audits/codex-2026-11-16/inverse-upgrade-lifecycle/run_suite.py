import os,sys,json,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
(HERE/'results').mkdir(exist_ok=True)
for label,spec in json.loads((HERE/sys.argv[1]).read_text()):
    out=HERE/'results'/label
    if Path(str(out)+'.time.json').exists():raise RuntimeError('Refusing overwrite '+label)
    spec=dict(spec,out=str(out));t=time.perf_counter();print('START',label,flush=True)
    with Path(str(out)+'.stdout').open('w') as o,Path(str(out)+'.stderr').open('w') as e:
        p=subprocess.run([sys.executable,str(HERE/spec.get('runner','run_star.py')),json.dumps(spec)],env=env,stdout=o,stderr=e)
    Path(str(out)+'.time.json').write_text(json.dumps(dict(returncode=p.returncode,wall_seconds=time.perf_counter()-t)))
    print('END',label,p.returncode,flush=True)
