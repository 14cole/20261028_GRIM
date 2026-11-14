"""Fresh-process control: PANELS [CAP|none] [adaptive|forecast-only]."""
import os,sys,json,time,resource,subprocess
from pathlib import Path
n=int(sys.argv[1]);cap=256 if len(sys.argv)<3 else None if sys.argv[2]=='none' else int(sys.argv[2])
policy=sys.argv[3] if len(sys.argv)>3 else 'adaptive'
if policy not in ('adaptive','forecast-only'):raise ValueError('Unknown sampling policy')
label='adaptive' if cap==256 else 'adaptive-no-cap' if cap is None else f'adaptive-cap-{cap}'
if policy=='forecast-only':label='sampling-baseline' if cap is None else f'forecast-only-cap-{cap}'
spec=dict(n=n,k=n/51.2,adaptive_sketch=policy=='adaptive',initial_rank_cap=cap,storage_budget_gib=10 if n>=32768 else 4,out=f'results/{label}-{n*2}')
env={**os.environ,'GRIM_ROOT':os.environ.get('GRIM_ROOT',str(Path('candidate').resolve())),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
if n>=32768 and Path('results/adaptive-32768.json').exists():
 with open('results/pre-large-comparison.stdout','w') as f:subprocess.run([sys.executable,'compare_results.py'],env=env,stdout=f,check=True)
before_usage=resource.getrusage(resource.RUSAGE_CHILDREN);started=time.perf_counter();monitor=None
with open(spec['out']+'.stdout','w') as o,open(spec['out']+'.stderr','w') as e:
 worker=subprocess.Popen([sys.executable,'compressed_control.py',json.dumps(spec)],env=env,stdout=o,stderr=e)
 if n>=32768:
  with open(spec['out']+'-monitor.stderr','w') as me:monitor=subprocess.Popen([sys.executable,'watch_rss.py',str(worker.pid),'14',spec['out']+'-monitor.json'],env=env,stdout=subprocess.DEVNULL,stderr=me)
 rc=worker.wait()
 if monitor:monitor.wait()
u=resource.getrusage(resource.RUSAGE_CHILDREN)
Path(spec['out']+'.time.json').write_text(json.dumps(dict(rc=rc,wall_seconds=time.perf_counter()-started,peak_gib=u.ru_maxrss/2**20,cpu_seconds=u.ru_utime+u.ru_stime-before_usage.ru_utime-before_usage.ru_stime,spec=spec,monitor_rc=monitor.returncode if monitor else None),indent=2))
if rc==0:Path(spec['out']+'.json').write_text(Path(spec['out']+'.stdout').read_text())
raise SystemExit(rc)
