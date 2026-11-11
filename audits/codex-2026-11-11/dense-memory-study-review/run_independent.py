import json,subprocess,sys,os,time
from pathlib import Path
scripts=Path(__file__).parent;root=sys.argv[1];p=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else scripts;p.mkdir(parents=True,exist_ok=True);cases=[]
core=[('pec8',dict(body='pec',n=8000),3.),('coated9720',dict(body='coated',n=6120),4.2),('airfoil3',dict(body='airfoil',f=3.),3.3),('pec14',dict(body='pec',n=14000),8.5),('diel8',dict(body='diel',n=4000),None)]
for rep in range(2):
 for name,spec,cap in core:
  variants=[('default',dict(storage='memory')),('lean',dict(storage='disk',options=dict(ram_budget_gib=cap)))]
  if rep%2:variants.reverse()
  for variant,opts in variants:cases.append(dict(spec,**opts,case=f'{name}-{variant}-{rep}'))
for name,opts in [('disk-paired',dict(storage='disk')),('memory-unpaired',dict(storage='memory',options=dict(ram_budget_gib=3.)))]:cases.append(dict(body='pec',n=8000,case='pec8-'+name,**opts))
for rep in range(2):
 for cap in ([3.4,2.8,2.2,1.9] if rep==0 else [1.9,2.2,2.8,3.4]):cases.append(dict(body='coated',n=6120,mode='automatic',options=dict(ram_budget_gib=cap),case=f'coated-auto-{cap}-{rep}'))
for name,spec,cap in core:
 if name=='airfoil3':continue
 cap={'pec8':2.,'coated9720':2.2,'pec14':5.5,'diel8':1.6}[name]
 cases.append(dict(spec,storage='disk',options=dict(ram_budget_gib=cap),case=name+'-disk-refused'))
(p/'cases.json').write_text(json.dumps(cases,indent=2))
out=p/'independent.jsonl';art=p/'runs';art.mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith('GHOST_')};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
for i,c in enumerate(cases):
 spec=dict(c,out=str(art/(c['case']+'.npz')))
 start=time.time();r=subprocess.run([sys.executable,str(scripts/'profile_independent.py'),root,json.dumps(spec)],capture_output=True,text=True,env=env,timeout=1200)
 (art/(c['case']+'.stderr')).write_text(r.stderr)
 rows=[x for x in r.stdout.splitlines() if x.startswith('{')]
 if not rows:raise RuntimeError((c,r.returncode,r.stderr[-1500:]))
 data=json.loads(rows[-1]);data['returncode']=r.returncode
 with out.open('a') as f:f.write(json.dumps(data)+'\n')
 print(i+1,len(cases),c['case'],data['wall'],data.get('peak_gib'),data.get('backend'),str(data['error'])[:110],flush=True)
print('DONE',flush=True)
