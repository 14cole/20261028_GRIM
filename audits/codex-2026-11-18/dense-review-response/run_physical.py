import os,sys,json,pathlib,subprocess
r=pathlib.Path(__file__).resolve().parent
roots=dict(main=os.environ.get('BASE_GRIM_ROOT','/workspace/production-consolidation/candidate'),old=os.environ.get('OLD_GRIM_ROOT','/workspace/postmerge-optimization/candidate'),direct=os.environ.get('DIRECT_GRIM_ROOT',str(r/'candidate')))
specs=[]
for threads in (1,4):
 for rep in range(2):
  for variant in (['main','old','direct'] if rep==0 else ['direct','old','main']):
   specs.append((f'partial-t{threads}-r{rep}-{variant}',dict(root=roots[variant],threads=threads,batch=16)))
for width in (1,180):
 for variant in ('direct','main'):
  specs.append((f'partial-t4-w{width}-{variant}',dict(root=roots[variant],threads=4,batch=width)))
for name,spec in specs:
 out=r/'fresh'/name;assert not out.with_suffix('.json').exists()
 spec=dict(spec,out=str(out),material='partial',shape='partial',length_m=.6,eps=[12.,-.01],frequency_ghz=5.,pol='TE')
 print('START',name,flush=True)
 with out.with_suffix('.log').open('w') as f:p=subprocess.run([sys.executable,str(r/'physical.py'),json.dumps(spec)],env=dict(os.environ,OPENBLAS_NUM_THREADS=str(spec['threads'])),stdout=f,stderr=subprocess.STDOUT)
 print('END',name,p.returncode,flush=True);assert p.returncode==0,name
