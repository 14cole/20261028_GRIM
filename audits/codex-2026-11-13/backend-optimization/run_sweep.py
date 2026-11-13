import os,sys,subprocess,json,time
from pathlib import Path
cases=[]
for n,k in [(1024,40),(2048,40),(4096,80)]:
 for leaf in [128,64]:
  cases.append(dict(n=n,k=k,leaf=leaf,out=f'results/leaf-{leaf}-{n}'))
for spec in cases:
 name=spec['out'];t=time.perf_counter()
 with open(name+'.json','w') as out,open(name+'.stderr','w') as err:
  p=subprocess.run([sys.executable,'compressed_control.py',json.dumps(spec)],stdout=out,stderr=err,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
 print(name,p.returncode,time.perf_counter()-t,flush=True)
 if p.returncode:raise SystemExit(p.returncode)
