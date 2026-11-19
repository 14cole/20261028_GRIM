"""Suite runner choosing the source tree per case (spec['tree']); records child peak RSS and return code."""
import os,sys,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;trees=json.loads(os.environ['TREES']);(HERE/'results').mkdir(exist_ok=True)
for label,spec in json.loads((HERE/sys.argv[1]).read_text()):
    out=HERE/'results'/label
    if Path(str(out)+'.time.json').exists():print('EXISTING',label,flush=True);continue
    spec=dict(spec,out=str(out));tree=spec.pop('tree');threads=str(spec.get('threads',1))
    env=dict(os.environ,GRIM_ROOT=trees[tree],OPENBLAS_NUM_THREADS=threads,OMP_NUM_THREADS=threads);print('START',label,flush=True)
    code="import resource,subprocess,sys,json,time;t=time.perf_counter();p=subprocess.run(sys.argv[2:]);print(json.dumps(dict(returncode=p.returncode,wall_seconds=time.perf_counter()-t,child_peak_gib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss/2**20)),file=open(sys.argv[1],'w'))"
    with Path(str(out)+'.stdout').open('w') as o,Path(str(out)+'.stderr').open('w') as e:
        rc=subprocess.run([sys.executable,'-c',code,str(out)+'.time.json',sys.executable,str(HERE/spec.get('runner')),json.dumps(spec)],env=env,stdout=o,stderr=e).returncode
    print('END',label,Path(str(out)+'.time.json').read_text().strip(),flush=True)
