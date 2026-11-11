import json,os,subprocess,sys
from pathlib import Path
here=Path(__file__).resolve().parent;out=here/'blas-results';out.mkdir(exist_ok=True)
roots={'base':sys.argv[1] if len(sys.argv)>1 else '/workspace/backend-simplification', 'new':sys.argv[2] if len(sys.argv)>2 else '/workspace/backend-performance'}
cases=[('pec4k',dict(body='pec',n=4000)),('diel4k',dict(body='diel',n=2000)),
       ('pec8k',dict(body='pec',n=8000)),('coated9720',dict(body='coated',n=6120))]
for rep in (1,2):
 for name,c in cases:
  if rep==2 and name in ('coated9720','pec8k'):continue
  for side in (('base','new') if rep==1 else ('new','base')):
   tag=f'{name}-{side}-r{rep}'
   spec=dict(c,backend='compressed',options=dict(assembly_threads=4,blas_threads='auto'),env={'GHOST_HMATRIX_MIN_UNKNOWNS':1024})
   print('START',tag,flush=True)
   p=subprocess.run([sys.executable,str(here/'case.py'),roots[side],json.dumps(spec)],
      env=dict(os.environ,REVIEW_RESULT_PATH=str(out/tag)),capture_output=True,text=True,timeout=1200)
   (out/(tag+'.stderr')).write_text(p.stderr)
   rows=[s for s in p.stdout.splitlines() if s.startswith('{')]
   r=json.loads(rows[-1]) if rows else dict(error=p.stderr[-2000:])
   r.update(tag=tag,returncode=p.returncode)
   with (out/'timings.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
   print('DONE',tag,r.get('wall'),r.get('error'),flush=True)
