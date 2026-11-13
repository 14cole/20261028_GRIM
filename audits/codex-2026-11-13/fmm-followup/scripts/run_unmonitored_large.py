import pathlib,psutil,time,json,os,subprocess
D=pathlib.Path(__file__).parent;names=['run_angle_cases.py','run_galerkin_cases.py','run_holdouts.py','run_extra_cases.py','rerun_low_frequency.py']
while any(p.info['cmdline'] and p.info['cmdline'][:2] in [['python',str(D/n)] for n in names] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
name='unmonitored-640-processes';spec=dict(ka=640,angles=61,strategy='processes',workers=4,batch=8,out=str(D/name));start=time.perf_counter()
with (D/(name+'.json')).open('w') as out,(D/(name+'.stderr')).open('w') as err:
 r=subprocess.run(['python',str(D/'angle_case.py'),json.dumps(spec)],stdout=out,stderr=err,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),timeout=600)
print(name,round(time.perf_counter()-start,2),r.returncode,flush=True)
