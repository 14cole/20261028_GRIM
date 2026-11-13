import os,pathlib,subprocess,psutil,time,sys
D=pathlib.Path(__file__).parent
while any(p.info['cmdline'] and p.info['cmdline'][:3]==['python',str(D/'run_suite.py'),'scale'] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
for args in [['run_suite.py','difficult'],['run_suite.py','low'],['run_suite.py','large'],['run_native_tuning.py']]:
 print('START',args,flush=True)
 r=subprocess.run([sys.executable,str(D/args[0]),*args[1:]],cwd=D,timeout=7200);print('DONE',args,r.returncode,flush=True)
 if r.returncode:break
