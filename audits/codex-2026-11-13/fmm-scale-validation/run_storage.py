import os,sys,subprocess,json,time,resource
from pathlib import Path
if len(sys.argv)>1:
 n=int(sys.argv[1]);label=sys.argv[2];spec=dict(n=n,k=n/51.2,op_tol=.01,inv_tol=.01,preconditioner_storage='complex64',native_pairs=True,profile=False,dense_reference=n<=2048,out='results/'+label)
 if label.endswith('tm'):spec.update(pol='TM',eps=[4.,0.],star=False)
 if label.endswith('lossy'):spec.update(eps=[3.,-.8])
 env={**os.environ,'GRIM_ROOT':os.environ.get('GRIM_ROOT',str(Path('candidate').resolve())),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'};start=time.perf_counter()
 with open(spec['out']+'.stdout','w') as o,open(spec['out']+'.stderr','w') as e:rc=subprocess.run([sys.executable,'native_fmm_control.py',json.dumps(spec)],env=env,stdout=o,stderr=e).returncode
 u=resource.getrusage(resource.RUSAGE_CHILDREN);Path(spec['out']+'.time.json').write_text(json.dumps(dict(rc=rc,wall_seconds=time.perf_counter()-start,peak_gib=u.ru_maxrss/2**20,spec=spec),indent=2));raise SystemExit(rc)
while not Path('results/fmm-65536.time.json').exists():time.sleep(2)
for n,label in [(2048,'storage-4096-te'),(2048,'storage-4096-tm'),(2048,'storage-4096-lossy'),(16384,'storage-32768-te')]:
 subprocess.run([sys.executable,__file__,str(n),label],check=True)
 with open('results/progress.log','a') as f:f.write(label+' completed\n')
