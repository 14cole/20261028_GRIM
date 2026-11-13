import pathlib,psutil,time,json,subprocess,os
from monitor_run import run
D=pathlib.Path(__file__).parent
waiting=['run_angle_cases.py','run_galerkin_cases.py']
while any(p.info['cmdline'] and p.info['cmdline'][:2] in [['python',str(D/name)] for name in waiting] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
for n,k,label in [(4000,[60.,0.],'stream'),(16000,[250.,0.],'16k'),(16000,[250.,2.],'16k-loss'),(64000,[1000.,0.],'64k')]:
 run('point-holdout-'+label,'point_case.py',dict(n=n,k=k,digits=10,separation=2,tile=512),timeout=600)
# Separate timing control without the psutil memory sampler.
for rep in range(2):
 for strategy in ['batch','threads','processes']:
  name=f'unmonitored-small-{strategy}-{rep}';spec=dict(ka=320,angles=32,strategy=strategy,workers=4 if strategy!='batch' else 1,batch=8,out=str(D/name));start=time.perf_counter()
  with (D/(name+'.json')).open('w') as out,(D/(name+'.stderr')).open('w') as err:
   r=subprocess.run(['python',str(D/'angle_case.py'),json.dumps(spec)],stdout=out,stderr=err,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),timeout=300)
  print(name,round(time.perf_counter()-start,2),r.returncode,flush=True)
