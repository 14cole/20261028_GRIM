import os,pathlib,sys,subprocess,json,time,psutil
D=pathlib.Path(__file__).parent;env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',LD_LIBRARY_PATH='/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu')
while any(p.info['cmdline'] and p.info['cmdline'][:2]==['python',str(D/'run_final_checks.py')] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
for name,spec in [(f'nodal-{shape}-512',dict(n=512,k=[40,-.8],shape=shape,mode='hybrid_nodal',tol=1e-13,full=True)) for shape in ['gap','coated','graded']]+[('symmetry-star-4096',dict(n=4096,k=[40,0],mode='stream_sym')),('transition-star-1500',dict(n=1500,k=[65.5,0],mode='hybrid_nodal',tol=1e-13,check_rows=[235,319]))]:
 spec['out']=str(D/name);t=time.perf_counter()
 with (D/(name+'.json')).open('w') as out,(D/(name+'.stderr')).open('w') as err:r=subprocess.run([sys.executable,str(D/'benchmark.py'),json.dumps(spec)],env=env,stdout=out,stderr=err,timeout=1200)
 (D/(name+'-run.json')).write_text(json.dumps(dict(exit_code=r.returncode,wall_seconds=time.perf_counter()-t)));print(name,r.returncode,time.perf_counter()-t,flush=True)
