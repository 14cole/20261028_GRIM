"""Serial fresh-process experiments: keep mesh, CPU count and pairing fixed."""
import os,sys,json,subprocess
from pathlib import Path
p=Path(__file__).parent;root=sys.argv[1];out=Path(sys.argv[2]) if len(sys.argv)>2 else p
(out/'runs').mkdir(parents=True,exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith('GHOST_')};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
cases=[]
for body,n,cap in [('pec',8000,3.),('coated',6120,4.2)]:
 for name,batch,extra in [('baseline',256,{}),('batch64',64,{}),('batch16',16,{}),('buffer64',64,dict(bounded_spool=True)),('trim64',64,dict(trim_after_factor=True)),('tile128',64,dict(tile=128))]:
  opts=dict(ram_budget_gib=cap,angle_batch_size=batch)
  extra=dict(extra)
  if 'tile' in extra:opts['assembly_tile']=extra.pop('tile')
  cases.append(dict(case=body+'-'+name,body=body,n=n,threads=4,storage='disk',force_unpaired=True,options=opts,**extra))
for body,n,cap in [('pec',8000,3.),('coated',6120,4.2)]:
 for name,combo in [('baseline-repeat',False),('combined-0',True),('combined-1',True)]:
  options=dict(ram_budget_gib=cap,angle_batch_size=64 if combo else 256)
  if combo:options['assembly_tile']=128
  cases.append(dict(case=body+'-'+name,body=body,n=n,threads=4,storage='disk',force_unpaired=True,options=options,bounded_spool=combo))
for body,n,cap in [('pec',8000,3.),('coated',6120,4.2)]:
 cases.append(dict(case=body+'-buffer256',body=body,n=n,threads=4,storage='disk',force_unpaired=True,bounded_spool=True,options=dict(ram_budget_gib=cap,angle_batch_size=256)))
(out/'memory-cases.json').write_text(json.dumps(cases,indent=2)+'\n')
for c in cases:
 if len(sys.argv)>3 and c['case'] not in sys.argv[3:]:continue
 spec=dict(c,out=str(out/'runs'/(c['case']+'.npz')))
 r=subprocess.run([sys.executable,str(p/'profile_opportunities.py'),root,json.dumps(spec)],env=env,capture_output=True,text=True,timeout=900)
 (out/'runs'/(c['case']+'.stderr')).write_text(r.stderr)
 rows=[x for x in r.stdout.splitlines() if x.startswith('{')]
 if not rows:raise RuntimeError((c,r.returncode,r.stderr[-2000:]))
 d=json.loads(rows[-1]);d['returncode']=r.returncode
 with (out/'memory-options.jsonl').open('a') as f:f.write(json.dumps(d)+'\n')
 print(c['case'],d['wall'],d['rss_highwater_gib'],d['error'],flush=True)
