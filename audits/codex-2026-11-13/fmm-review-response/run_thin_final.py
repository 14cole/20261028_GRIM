import pathlib,time,psutil,subprocess,os
D=pathlib.Path(__file__).parent
while any(p.info['cmdline'] and p.info['cmdline'][:2]==['python',str(D/'run_diagnostics.py')] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
with (D/'thin-final.log').open('w') as out:
 r=subprocess.run(['python',str(D/'thin_diagnostic.py'),'/workspace/grim-fmm-followup'],stdout=out,stderr=subprocess.STDOUT,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),timeout=900);print(r.returncode)
