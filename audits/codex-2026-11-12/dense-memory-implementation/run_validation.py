"""Fresh-process measurements; four CPUs, complete fields and admission evidence."""
import json, os, subprocess, sys
from pathlib import Path
p=Path(__file__).resolve().parent
root=Path(sys.argv[1]).resolve()
cases=[
 dict(case='airfoil-adaptive',body='airfoil',f=3.,certified=True,options=dict(factorization='automatic',mesh_strategy='adaptive')),
 dict(case='pec8000-dense-2g',body='pec',n=8000,options=dict(ram_budget_gib=2.0)),
 dict(case='coated9720-dense-2g',body='coated',n=6120,options=dict(ram_budget_gib=2.0)),
 dict(case='coated9720-dense-2.2g',body='coated',n=6120,options=dict(ram_budget_gib=2.2)),
 dict(case='coated9720-compressed-2.8g',body='coated',n=6120,mode='compressed',options=dict(ram_budget_gib=2.8)),
 dict(case='coated9720-compressed-1.9g',body='coated',n=6120,mode='compressed',options=dict(ram_budget_gib=1.9)),
 dict(case='pec8000-memory',body='pec',n=8000,storage='memory'),
 dict(case='coated9720-memory',body='coated',n=6120,storage='memory'),
 dict(case='pec8000-disk',body='pec',n=8000,storage='disk'),
 dict(case='coated9720-disk',body='coated',n=6120,storage='disk'),
 dict(case='pec8000-dense-1.5g',body='pec',n=8000,options=dict(ram_budget_gib=1.5)),
 dict(case='coated9720-auto-2g',body='coated',n=6120,mode='automatic',options=dict(ram_budget_gib=2.0)),
 dict(case='coated9720-auto-2.8g',body='coated',n=6120,mode='automatic',options=dict(ram_budget_gib=2.8)),
]
env={k:v for k,v in os.environ.items() if not k.startswith('GHOST_')}
env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
(p/'results').mkdir(exist_ok=True)
for case in cases:
 if len(sys.argv)>2 and case['case'] not in sys.argv[2:]:continue
 spec=dict(case,allocation_cpus=4,out=str(p/'results'/(case['case']+'.npz')))
 command=[sys.executable,str(p/'allocation_wrapper.py'),str(root),str(p/'profile_solve.py'),json.dumps(spec)]
 done=subprocess.run(command,env=env,capture_output=True,text=True,timeout=1200)
 (p/'results'/(case['case']+'.stderr')).write_text(done.stderr)
 rows=[row for row in done.stdout.splitlines() if row.startswith('{')]
 if not rows:raise RuntimeError((done.returncode,done.stderr[-2000:]))
 value=json.loads(rows[-1]);value['returncode']=done.returncode
 (p/'results'/(case['case']+'.json')).write_text(json.dumps(value,indent=2)+'\n')
 print(case['case'],value['wall'],value['peak_gib'],value['error'],flush=True)
