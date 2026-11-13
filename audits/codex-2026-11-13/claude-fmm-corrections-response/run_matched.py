import os,sys,time,resource,subprocess,json
from pathlib import Path
# Each measuring parent owns exactly one child, so RUSAGE_CHILDREN is per case.
if len(sys.argv)>1:
 kind=sys.argv[1];name='matched-'+kind;spec=dict(n=4096,k=80,pol='TE',out='results/'+name)
 if kind=='fmm':spec.update(op_tol=.01,inv_tol=.01,detach_operator=True)
 start=time.perf_counter()
 with open('results/'+name+'.json','w') as out,open('results/'+name+'.stderr','w') as err:
  rc=subprocess.run([sys.executable,'native_context.py',kind,json.dumps(spec)],stdout=out,stderr=err).returncode
 usage=resource.getrusage(resource.RUSAGE_CHILDREN)
 Path('results/'+name+'.time.json').write_text(json.dumps(dict(rc=rc,wall_s=time.perf_counter()-start,peak_gib=usage.ru_maxrss/2**20,cpu_s=usage.ru_utime+usage.ru_stime,spec=spec),indent=2))
 raise SystemExit(rc)
for kind in ['compressed','fmm','dense']:
 subprocess.run([sys.executable,__file__,kind],check=True)
 print(kind+' complete',flush=True)
