import pathlib,sys,psutil,time,subprocess,os,json
D=pathlib.Path(__file__).parent;env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',LD_LIBRARY_PATH='/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu')
while any(p.info['cmdline'] and p.info['cmdline'][:2]==['python',str(D/'run_extensions.py')] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
for script,args in [('coated_quadrature.py',['/workspace/grim-fmm-followup']),('structural_checks.py',[])]:
 with (D/(script+'.log')).open('w') as out:r=subprocess.run([sys.executable,str(D/script),*args],stdout=out,stderr=subprocess.STDOUT,env=env,timeout=600)
 print(script,r.returncode,flush=True)
# This case was added after the extension scheduler was already loaded.
c=dict(n=512,k=[40,-.8],shape='gap',mode='stream_sym',full=True,out=str(D/'symmetry-gap-512'))
with (D/'symmetry-gap-512.json').open('w') as out,(D/'symmetry-gap-512.stderr').open('w') as err:r=subprocess.run([sys.executable,str(D/'benchmark.py'),json.dumps(c)],stdout=out,stderr=err,env=env,timeout=600)
print('symmetry-gap',r.returncode,flush=True)
