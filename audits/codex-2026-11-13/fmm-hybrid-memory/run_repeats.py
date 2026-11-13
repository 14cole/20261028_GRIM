import pathlib,os,sys,json,time,subprocess,psutil,resource
D=pathlib.Path(__file__).parent
while any(p.info['cmdline'] and p.info['cmdline'][:2]==['python',str(D/'run_last_comparisons.py')] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
name='compressed-full-star-1536';spec=dict(n=1536,k=[40,0],mode='hybrid_nodal',tol=1e-13,full=True,require_compression=True,out=str(D/name));t=time.perf_counter()
with (D/(name+'.json')).open('w') as out,(D/(name+'.stderr')).open('w') as err:r=subprocess.run([sys.executable,str(D/'benchmark.py'),json.dumps(spec)],stdout=out,stderr=err,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',LD_LIBRARY_PATH='/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu'),timeout=1200)
(D/(name+'-run.json')).write_text(json.dumps(dict(exit_code=r.returncode,wall_seconds=time.perf_counter()-t)));print(name,r.returncode,time.perf_counter()-t,flush=True)
for imag in [-.8,0]:
 for div in [25,100]:
  name=f'native-repeat-4096-{imag}-{div}';spec=dict(n=4096,k=[40,imag],mode='native_tuned',ndiv=div,warmups=1,repeats=5,out=str(D/name));t=time.perf_counter();usage=resource.getrusage(resource.RUSAGE_CHILDREN)
  with (D/(name+'.json')).open('w') as out,(D/(name+'.stderr')).open('w') as err:r=subprocess.run([sys.executable,str(D/'benchmark.py'),json.dumps(spec)],stdout=out,stderr=err,env=dict(os.environ,FMM_NDIV=str(div),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',LD_LIBRARY_PATH='/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu'),timeout=1200)
  now=resource.getrusage(resource.RUSAGE_CHILDREN);result=dict(exit_code=r.returncode,wall_seconds=time.perf_counter()-t,user_cpu_seconds=now.ru_utime-usage.ru_utime,system_cpu_seconds=now.ru_stime-usage.ru_stime);(D/(name+'-run.json')).write_text(json.dumps(result));print(name,result,flush=True)
  if r.returncode:break
