import json,sys,os,subprocess
from pathlib import Path
p=Path(__file__).parent;root=sys.argv[1];out=Path(sys.argv[2]) if len(sys.argv)>2 else p
(out/'geometry').mkdir(parents=True,exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith('GHOST_')};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
cases=[dict(case='fragmented',parts=256,ppw=20)]
cases += [dict(case='merged-ppw'+str(ppw),parts=1,ppw=ppw) for ppw in (20,40,80,160)]
cases += [dict(case='merged-p'+str(degree),parts=1,ppw=40,degree=degree,coarsening=4.) for degree in (2,3)]
(out/'geometry-cases.json').write_text(json.dumps(cases,indent=2)+'\n')
for c in cases:
 c=dict(c,out=str(out/'geometry'/(c['case']+'.npz')))
 r=subprocess.run([sys.executable,str(p/'profile_geometry.py'),root,json.dumps(c)],capture_output=True,text=True,env=env,timeout=900)
 (out/'geometry'/(c['case']+'.stderr')).write_text(r.stderr)
 rows=[s for s in r.stdout.splitlines() if s.startswith('{')]
 if not rows:raise RuntimeError((c,r.stderr[-2000:]))
 d=json.loads(rows[-1]);d['returncode']=r.returncode
 with (out/'geometry.jsonl').open('a') as f:f.write(json.dumps(d)+'\n')
 print(c['case'],d['wall'],[v['n'] for v in d['factors']],d['error'],flush=True)
