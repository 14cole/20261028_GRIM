import pathlib,json,os,subprocess,time,sys,psutil
D=pathlib.Path(__file__).parent
while any(p.info['cmdline'] and p.info['cmdline'][:2]==['python',str(D/'run_after_remaining.py')] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
cases=[dict(n=128,k=[12,0],mode='stream_sym',full=True),dict(n=512,k=[40,-.8],shape='coated',mode='stream_sym',full=True),dict(n=2048,k=[40,0],mode='stream_sym'),dict(n=2048,k=[40,0],mode='hybrid',tol=1e-13)]
for i,c in enumerate(cases):
 name=f'extension-{i}-{c["n"]}-{c["mode"]}';c['out']=str(D/name);t=time.perf_counter()
 with (D/(name+'.json')).open('w') as out,(D/(name+'.stderr')).open('w') as err:
  r=subprocess.run([sys.executable,str(D/'benchmark.py'),json.dumps(c)],env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',LD_LIBRARY_PATH='/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu'),stdout=out,stderr=err,timeout=1200)
 (D/(name+'-run.json')).write_text(json.dumps(dict(exit_code=r.returncode,wall_seconds=time.perf_counter()-t)));print(name,r.returncode,time.perf_counter()-t,flush=True)
 if r.returncode:break
