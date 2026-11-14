"""Fresh-process 65k Compressed control, larger disclosed storage allowance."""
import os,sys,json,time,resource,subprocess
from pathlib import Path
spec=dict(n=32768,k=640.,storage_budget_gib=10,out='results/compressed-65536')
env={**os.environ,'GRIM_ROOT':os.environ.get('GRIM_ROOT',str(Path('candidate').resolve())),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
started=time.perf_counter()
with open(spec['out']+'.stdout','w') as o,open(spec['out']+'.stderr','w') as e:
 rc=subprocess.run([sys.executable,'compressed_control.py',json.dumps(spec)],env=env,stdout=o,stderr=e).returncode
u=resource.getrusage(resource.RUSAGE_CHILDREN)
Path(spec['out']+'.time.json').write_text(json.dumps(dict(rc=rc,wall_seconds=time.perf_counter()-started,peak_gib=u.ru_maxrss/2**20,cpu_seconds=u.ru_utime+u.ru_stime,spec=spec),indent=2))
if rc==0:Path(spec['out']+'.json').write_text(Path(spec['out']+'.stdout').read_text())
raise SystemExit(rc)
