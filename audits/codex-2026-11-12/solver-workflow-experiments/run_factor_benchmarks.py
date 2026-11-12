import json,os,signal,subprocess,sys,time,shutil
from pathlib import Path
import psutil
P=Path(__file__).resolve().parent;(P/'factor_results').mkdir(exist_ok=True)
for name in ['pec4k','diel4k','pec8k']:
 for variant in (['dense','disk512','fused512','dense_refined','fused512_refined'] if name=='pec8k' else ['dense','disk128','disk512','fused512','mixed','scaled_mixed']):
  out=P/'factor_results'/f'{name}-{variant}'
  if out.with_suffix('.json').exists():continue
  with open(str(out)+'.stdout','w') as stdout,open(str(out)+'.stderr','w') as stderr:
   env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');start=time.monotonic();reason=None
   child=subprocess.Popen([sys.executable,str(P/'factor_benchmark.py'),str(P/'matrices'/f'{name}.npy'),variant,str(out),sys.argv[1]],stdout=stdout,stderr=stderr,env=env,start_new_session=True)
   while child.poll() is None:
    if time.monotonic()-start>300:reason='300s timeout'
    try:
     if psutil.Process(child.pid).memory_info().rss>8*2**30:reason='8 GiB RSS limit'
    except psutil.Error:pass
    if reason:os.killpg(child.pid,signal.SIGTERM);child.wait();break
    time.sleep(.2)
  for directory in P.glob('scratch-factor-'+out.name+'-*'):
   if directory.is_dir():shutil.rmtree(directory)
  if reason or child.returncode:out.with_suffix('.json').write_text(json.dumps(dict(error=reason or f'exit {child.returncode}',variant=variant,source=name)))
  r=json.loads(out.with_suffix('.json').read_text());print(name,variant,r.get('wall_seconds'),r.get('peak_rss_gib'),r['error'],flush=True)
