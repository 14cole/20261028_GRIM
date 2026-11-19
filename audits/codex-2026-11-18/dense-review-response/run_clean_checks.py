import os,sys,pathlib,json,subprocess
r=pathlib.Path(__file__).resolve().parent
for nt,st in ((1,1),(4,4),(1,4)):
 name=f'clean-pools-{nt}-{st}-w16';out=r/'fresh'/name
 assert not out.with_suffix('.json').exists()
 spec=dict(np_threads=nt,sp_threads=st,width=16,out=str(out))
 print('START',name,flush=True)
 with out.with_suffix('.log').open('w') as f:p=subprocess.run([sys.executable,str(r/'interleaved_check.py'),json.dumps(spec)],env=dict(os.environ,OPENBLAS_NUM_THREADS='1'),stdout=f,stderr=subprocess.STDOUT)
 print('END',name,p.returncode,flush=True);assert p.returncode==0
