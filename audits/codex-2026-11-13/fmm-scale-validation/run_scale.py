"""Serial fresh-process controls; external wall and high-water RSS per case."""
import os,sys,json,time,resource,subprocess
from pathlib import Path
env={**os.environ,'GRIM_ROOT':os.environ.get('GRIM_ROOT',str(Path('candidate').resolve())),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
if len(sys.argv)>1:
    method=sys.argv[1];n=int(sys.argv[2]);out=f'results/{method}-{n*2}'
    spec=dict(n=n,k=n/51.2,out=out)
    script='compressed_control.py'
    if method=='fmm':
        spec.update(op_tol=.01,inv_tol=.01,detach_operator=True,native_pairs=True,profile=False,dense_reference=False)
        script='reproduce_baseline.py' if n==16384 else 'native_fmm_control.py'
    start=time.perf_counter()
    with open(out+'.stdout','w') as o,open(out+'.stderr','w') as e:
        rc=subprocess.run([sys.executable,script,json.dumps(spec)],env=env,stdout=o,stderr=e).returncode
    u=resource.getrusage(resource.RUSAGE_CHILDREN)
    Path(out+'.time.json').write_text(json.dumps(dict(rc=rc,wall_seconds=time.perf_counter()-start,peak_gib=u.ru_maxrss/2**20,cpu_seconds=u.ru_utime+u.ru_stime,spec=spec),indent=2))
    if method=='compressed' and rc==0:Path(out+'.json').write_text(Path(out+'.stdout').read_text())
    raise SystemExit(rc)
for method,n in [('fmm',16384),('compressed',16384),('fmm',32768)]:
    subprocess.run([sys.executable,__file__,method,str(n)],check=True)
    # Persist progress instead of relying on the lifetime of a UI stdout pipe.
    with open('results/progress.log','a') as f:f.write(f'{method} {n*2} completed\n')
