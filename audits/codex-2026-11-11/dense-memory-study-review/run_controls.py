"""Original-profiler and explicit four-CPU controls for borderline conclusions."""
import json,subprocess,sys,os
from pathlib import Path
import numpy as np
scripts=Path(__file__).parent;root=sys.argv[1];p=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else scripts
p.mkdir(parents=True,exist_ok=True);art=p/'controls';art.mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith('GHOST_')};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
cases=[dict(case='claude-unmodified-auto-'+str(cap),body='coated',n=6120,mode='automatic',options=dict(ram_budget_gib=cap)) for cap in (2.2,2.4,2.8)]
cases += [dict(case='four-cpu-coated-auto-2.2',body='coated',n=6120,mode='automatic',options=dict(ram_budget_gib=2.2),allocation_cpus=4),
 dict(case='four-cpu-airfoil-lean',body='airfoil',f=3.,storage='disk',options=dict(ram_budget_gib=3.3),allocation_cpus=4),
 dict(case='four-cpu-airfoil-compressed',body='airfoil',f=3.,mode='compressed',options=dict(ram_budget_gib=3.3),allocation_cpus=4)]
cases += [dict(case='four-cpu-airfoil-default',body='airfoil',f=3.,storage='memory',allocation_cpus=4),
 dict(case='four-cpu-airfoil-memory-unpaired',body='airfoil',f=3.,storage='memory',options=dict(ram_budget_gib=3.3),allocation_cpus=4)]
(p/'control-cases.json').write_text(json.dumps(cases,indent=2))
for c in cases:
 if len(sys.argv)>3 and c['case'] not in sys.argv[3:]:continue
 name=c['case'];spec=dict(c,out=str(art/(name+'.npz')))
 profiler=str(scripts/'claude/profile_dense.py')
 command=[sys.executable,profiler,root,json.dumps(spec)]
 if c.get('allocation_cpus'):
  command=[sys.executable,str(scripts/'allocation_wrapper.py'),root,profiler,json.dumps(spec)]
 r=subprocess.run(command,capture_output=True,text=True,env=env,timeout=1200)
 (art/(name+'.stderr')).write_text(r.stderr)
 rows=[x for x in r.stdout.splitlines() if x.startswith('{')]
 if not rows:raise RuntimeError((c,r.returncode,r.stderr[-1000:]))
 d=json.loads(rows[-1]);d['returncode']=r.returncode
 if d['error'] is None:
  reference='coated9720' if c['body']=='coated' else 'airfoil3'
  a=np.load(art/(name+'.npz'))['field'];b=np.load(p/'runs'/(reference+'-default-0.npz'))['field']
  assert a.shape==b.shape and np.isfinite(a).all()
  err=float(np.max(abs(a-b))/np.max(abs(b)))
  d['field_threshold']=1e-6 if d['backend']!='cpu' else 1e-11
  d['field_check_passed']=err<d['field_threshold']
  d['full_field_relative_error']=err;d['field_count']=len(a)
 with (p/'controls.jsonl').open('a') as f:f.write(json.dumps(d)+'\n')
 print(name,d['wall'],d['peak_gib'],str(d['error'])[:130],flush=True)
print('DONE',flush=True)
