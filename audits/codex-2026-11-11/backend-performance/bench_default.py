import json,os,subprocess,sys
from pathlib import Path
here=Path(__file__).resolve().parent;out=here/'default-results';out.mkdir(exist_ok=True)
roots={'base':sys.argv[1] if len(sys.argv)>1 else '/workspace/backend-simplification', 'new':sys.argv[2] if len(sys.argv)>2 else '/workspace/backend-performance'}
cases=[('pec4k',dict(body='pec',n=4000)),('diel4k',dict(body='diel',n=2000)),
       ('coated6480',dict(body='coated',n=4080)),('pec8k',dict(body='pec',n=8000)),
       ('diel8k',dict(body='diel',n=4000)),('pec12k',dict(body='pec',n=12000)),
       ('dense10k',dict(body='pec',n=10000))]
for rep in (1,2):
 for name,c in cases:
  if rep==2 and name not in ('pec4k','diel4k'):continue
  for side in (('base','new') if rep==1 else ('new','base')):
   tag=f'{name}-{side}-r{rep}'
   backend='dense' if name=='dense10k' else ('compressed' if side=='base' else 'automatic')
   spec=dict(c,backend=backend,options=dict(assembly_threads=4,blas_threads='auto',compressed_storage_mib=0))
   print('START',tag,flush=True)
   p=subprocess.run([sys.executable,str(here/'case.py'),roots[side],json.dumps(spec)],
      env=dict(os.environ,REVIEW_RESULT_PATH=str(out/tag)),capture_output=True,text=True,timeout=1200)
   (out/(tag+'.stderr')).write_text(p.stderr)
   rows=[s for s in p.stdout.splitlines() if s.startswith('{')]
   r=json.loads(rows[-1]) if rows else dict(error=p.stderr[-2000:])
   r.update(tag=tag,returncode=p.returncode)
   with (out/'timings.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
   print('DONE',tag,r.get('wall'),r.get('linear_backend'),r.get('error'),flush=True)
