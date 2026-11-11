"""Serial follow-up experiments; deliberately separate from production timings."""
import json,subprocess,sys,os
from pathlib import Path
scripts=Path(__file__).parent;root=sys.argv[1];p=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else scripts;p.mkdir(parents=True,exist_ok=True);art=p/'diagnostics';art.mkdir(exist_ok=True)
cases=[dict(body='pec',n=8000,storage='disk',options=dict(ram_budget_gib=2.),case='pec8-lean-model-2',forecast_probe=True,lean_forecast=True),
 dict(body='coated',n=6120,storage='disk',options=dict(ram_budget_gib=2.2),case='coated-lean-model-2.2',forecast_probe=True,lean_forecast=True),
 dict(body='coated',n=6120,storage='disk',options=dict(ram_budget_gib=1.9),case='coated-lean-model-1.9',forecast_probe=True,lean_forecast=True),
 dict(body='diel',n=4000,storage='disk',options=dict(ram_budget_gib=1.6),case='diel8-lean-model-1.6',forecast_probe=True,lean_forecast=True),
 dict(body='pec',n=14000,storage='disk',options=dict(ram_budget_gib=5.5),case='pec14-lean-model-5.5',forecast_probe=True,lean_forecast=True),
 dict(body='pec',n=8000,storage='disk',options=dict(ram_budget_gib=3.),case='pec8-trace-4threads',trace_allocations=True,forecast_probe=True),
 dict(body='pec',n=8000,storage='disk',threads=1,options=dict(ram_budget_gib=3.),case='pec8-trace-1thread',trace_allocations=True,forecast_probe=True)]
comparisons=[dict(body='coated',n=6120,mode='automatic',options=dict(ram_budget_gib=2.4),case=f'coated-auto-2.4-{rep}') for rep in range(2)]
for rep in range(2):
 comparisons.append(dict(body='pec',n=14000,mode='automatic',options=dict(ram_budget_gib=8.5),case=f'pec14-compressed-{rep}'))
 comparisons.append(dict(body='airfoil',f=3.,mode='compressed',options=dict(ram_budget_gib=3.3),case=f'airfoil-compressed-{rep}'))
comparisons.append(dict(body='pec',n=8000,storage='auto',options=dict(ram_budget_gib=2.4),case='pec8-auto-residual-2.4'))
cases.append(dict(body='diel',n=4000,storage='disk',options=dict(ram_budget_gib=2.),case='diel8-lean-model-2',forecast_probe=True,lean_forecast=True))
cases=comparisons+cases+[dict(body='coated',n=6120,mode='automatic',options=dict(ram_budget_gib=cap),case=f'coated-bounded-projection-{cap}',chunk_projection=True) for cap in (2.8,1.9)]
(p/'diagnostic-cases.json').write_text(json.dumps(cases,indent=2))
env={k:v for k,v in os.environ.items() if not k.startswith('GHOST_')};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
for c in cases:
 spec=dict(c,out=str(art/(c['case']+'.npz')))
 r=subprocess.run([sys.executable,str(scripts/'profile_diagnostic.py'),root,json.dumps(spec)],capture_output=True,text=True,env=env,timeout=1200)
 (art/(c['case']+'.stderr')).write_text(r.stderr)
 rows=[x for x in r.stdout.splitlines() if x.startswith('{')]
 if not rows:raise RuntimeError((c,r.returncode,r.stderr[-1500:]))
 data=json.loads(rows[-1]);data['returncode']=r.returncode
 with (p/'diagnostic.jsonl').open('a') as f:f.write(json.dumps(data)+'\n')
 print(c['case'],data['wall'],data['peak_gib'],data.get('backend'),str(data['error'])[:150],flush=True)
for script in ('test_residual_safety.py','test_workflows.py'):
 r=subprocess.run([sys.executable,str(scripts/script),root,str(p)],capture_output=True,text=True,env=env,timeout=1200)
 (p/(script+'.log')).write_text(r.stdout+r.stderr);print(script,r.returncode,r.stdout[-100:],r.stderr[-500:],flush=True)
 if r.returncode:raise RuntimeError(script)
print('DONE',flush=True)
