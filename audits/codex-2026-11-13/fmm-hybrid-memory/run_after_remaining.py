import pathlib,subprocess,psutil,time,sys
D=pathlib.Path(__file__).parent
while any(p.info['cmdline'] and p.info['cmdline'][:2]==['python',str(D/'run_remaining.py')] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
r=subprocess.run([sys.executable,str(D/'run_systems.py')],cwd=D,timeout=7200);print('systems done',r.returncode,flush=True)
