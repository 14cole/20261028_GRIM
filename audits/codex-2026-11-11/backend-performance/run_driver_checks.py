import concurrent.futures,json,os,subprocess,sys
from pathlib import Path
here=Path(__file__).resolve().parent
def run(spec):
 kind,certified=spec;tag=f'{kind}-{certified}';output=here/'drivers'/tag
 with (here/(tag+'.log')).open('w') as log:
  p=subprocess.run([sys.executable,str(here/'driver_end_to_end.py'),(sys.argv[1] if len(sys.argv)>1 else '/workspace/backend-performance'),kind,str(output),str(certified)],
      stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),timeout=900)
 return dict(case=tag,rc=p.returncode)
specs=[(kind,c) for kind in ('local-twod','hpc-twod','local-bor','hpc-bor') for c in (0,1)]
with concurrent.futures.ThreadPoolExecutor(2) as pool:
 rows=list(pool.map(run,specs))
(here/'driver-status.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows),flush=True)
assert all(r['rc']==0 for r in rows)
