"""Two more matched four-thread pairs after initial production results were inconclusive."""
import os,sys,pathlib,json,subprocess
r=pathlib.Path(__file__).resolve().parent
roots=dict(main=os.environ.get('BASE_GRIM_ROOT','/workspace/production-consolidation/candidate'),direct=os.environ.get('DIRECT_GRIM_ROOT',str(r/'candidate')))
for rep in (2,3):
 for variant in (('main','direct') if rep==2 else ('direct','main')):
  name=f'partial-t4-r{rep}-{variant}';out=r/'fresh'/name;assert not out.with_suffix('.json').exists()
  spec=dict(root=roots[variant],threads=4,batch=16,out=str(out),material='partial',shape='partial',length_m=.6,eps=[12.,-.01],frequency_ghz=5.,pol='TE')
  print('START',name,flush=True)
  with out.with_suffix('.log').open('w') as f:p=subprocess.run([sys.executable,str(r/'physical.py'),json.dumps(spec)],env=dict(os.environ,OPENBLAS_NUM_THREADS='4'),stdout=f,stderr=subprocess.STDOUT)
  print('END',name,p.returncode,flush=True);assert p.returncode==0
