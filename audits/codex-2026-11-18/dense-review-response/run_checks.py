import pathlib,json,sys,subprocess,os
r=pathlib.Path(__file__).resolve().parent
cases=[]
for t in (1,2,4,8):cases.append((f'pools-{t}-{t}-w16',dict(np_threads=t,sp_threads=t,width=16)))
cases += [('pools-1-4-w16',dict(np_threads=1,sp_threads=4,width=16)),('pools-4-1-w16',dict(np_threads=4,sp_threads=1,width=16)),('pools-4-4-w180',dict(np_threads=4,sp_threads=4,width=180)),('pools-4-4-w1',dict(np_threads=4,sp_threads=4,width=1))]
for name,spec in cases:
 out=r/'fresh'/name;assert not out.with_suffix('.json').exists()
 spec=dict(spec,out=str(out));print('START',name,flush=True)
 with out.with_suffix('.log').open('w') as f:
  p=subprocess.run([sys.executable,str(r/'interleaved_check_initial.py'),json.dumps(spec)],env=dict(os.environ,OPENBLAS_NUM_THREADS='1'),stdout=f,stderr=subprocess.STDOUT)
 print('END',name,p.returncode,flush=True);assert p.returncode==0,name
