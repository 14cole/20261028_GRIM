import json,os,pathlib,subprocess,time,sys
D=pathlib.Path(__file__).parent
for n,k in [(2048,[40,0]),(4096,[40,-.8])]:
 for div in [25,100,400]:
  name=f'native-ndiv-{n}-{div}';spec=dict(n=n,k=k,mode='native_tuned',ndiv=div,out=str(D/name));t=time.perf_counter()
  with (D/(name+'.json')).open('w') as out,(D/(name+'.stderr')).open('w') as err:
   r=subprocess.run([sys.executable,str(D/'benchmark.py'),json.dumps(spec)],env=dict(os.environ,FMM_NDIV=str(div),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',LD_LIBRARY_PATH='/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu'),stdout=out,stderr=err,timeout=1200)
  (D/(name+'-run.json')).write_text(json.dumps(dict(exit_code=r.returncode,wall_seconds=time.perf_counter()-t)));print(name,r.returncode,time.perf_counter()-t,flush=True)
  if r.returncode:raise SystemExit(r.returncode)
