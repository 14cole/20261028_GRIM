import os,pathlib,sys,subprocess,time,psutil,json,hashlib
D=pathlib.Path(__file__).parent;env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',LD_LIBRARY_PATH='/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu')
while any(p.info['cmdline'] and p.info['cmdline'][:2]==['python',str(D/'run_repeats.py')] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
for script in ['panel_projection_proof.py','analyze_study.py']:
 with (D/(script+'.log')).open('w') as out:r=subprocess.run([sys.executable,str(D/script)],env=env,stdout=out,stderr=subprocess.STDOUT,timeout=600)
 print(script,r.returncode,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
identities={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(D.glob('*.py'))};(D/'SOURCE_IDENTITIES.json').write_text(json.dumps(identities,indent=2)+'\n')
