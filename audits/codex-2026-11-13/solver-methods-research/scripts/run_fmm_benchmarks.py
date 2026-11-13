import pathlib,json,os,subprocess,time
D=pathlib.Path(__file__).parent
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',LD_LIBRARY_PATH='/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu')
for n,ghz,rhs in [(2000,2,1),(8000,2,1),(32000,2,1),(128000,2,1),(8000,15,1),(32000,15,1),(128000,15,1),(8000,2,8),(8000,2,32)]:
 name=f'fmm-points-{n}-{ghz}-{rhs}';p=D/(name+'.json')
 if p.exists() and p.stat().st_size:continue
 spec=dict(n=n,ghz=ghz,rhs=rhs,eps=1e-12,out=str(D/(name+'.npy')))
 with p.open('w') as f:
  try:r=subprocess.run(['python',str(D/'fmm_point_benchmark.py'),json.dumps(spec)],stdout=f,stderr=subprocess.PIPE,text=True,env=env,timeout=180)
  except subprocess.TimeoutExpired:p.write_text(json.dumps(dict(spec,error='TimeoutExpired after 180s')));print(name,'TIMEOUT',flush=True);continue
 if r.stderr:(D/(name+'.stderr')).write_text(r.stderr)
 try:result=json.loads(p.read_text());print(name,result.get('seconds'),result.get('sampled_relative_max'),result.get('error'),flush=True)
 except Exception:print(name,'invalid output',flush=True)
