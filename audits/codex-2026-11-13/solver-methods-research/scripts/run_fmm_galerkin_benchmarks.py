import subprocess,os,json,time,pathlib
D=pathlib.Path(__file__).parent
for n,ghz in [(4000,2),(16000,2),(4000,15),(16000,15)]:
 name=f'fmm-galerkin-{n}-{ghz}';p=D/(name+'.json');spec=dict(n=n,ghz=ghz,out=str(D/name))
 if p.exists() and p.stat().st_size:continue
 start=time.perf_counter()
 with p.open('w') as f:
  try:r=subprocess.run(['python',str(D/'fmm_galerkin_benchmark.py'),json.dumps(spec)],stdout=f,stderr=subprocess.PIPE,text=True,timeout=300,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',LD_LIBRARY_PATH='/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu'))
  except subprocess.TimeoutExpired:p.write_text(json.dumps(dict(spec,error='timeout')));print(name,'timeout',flush=True);continue
 if r.stderr:(D/(name+'.stderr')).write_text(r.stderr)
 print(name,round(time.perf_counter()-start,2),r.returncode,flush=True)
