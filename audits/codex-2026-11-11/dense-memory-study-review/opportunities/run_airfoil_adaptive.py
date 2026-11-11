"""Existing production hp adaptation, with full quality gates; no geometry edits."""
import sys,json,subprocess,os
from pathlib import Path
p=Path(__file__).parent;root=sys.argv[1];out=Path(sys.argv[2]) if len(sys.argv)>2 else p
(out/'airfoil').mkdir(exist_ok=True,parents=True)
env={k:v for k,v in os.environ.items() if not k.startswith('GHOST_')};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
for name,adaptive in [('global',False),('adaptive-certified',True),('adaptive-certified-repeat',True),('global-repeat',False),('adaptive-coarsen4',True),('adaptive-coarsen6',True)]:
 if len(sys.argv)>3 and name not in sys.argv[3:]:continue
 spec=dict(case=name,body='airfoil',f=3.,threads=4,storage='disk',force_unpaired=True,certified=adaptive,options=dict(ram_budget_gib=12.,mesh_strategy='adaptive' if adaptive else 'global'),out=str(out/'airfoil'/(name+'.npz')))
 if name.startswith('adaptive-coarsen'):spec['hp_coarsening']=float(name.rsplit('coarsen',1)[1])
 r=subprocess.run([sys.executable,str(p/'profile_opportunities.py'),root,json.dumps(spec)],env=env,capture_output=True,text=True,timeout=1200)
 (out/'airfoil'/(name+'.stderr')).write_text(r.stderr)
 lines=[x for x in r.stdout.splitlines() if x.startswith('{')]
 if not lines:raise RuntimeError((r.returncode,r.stderr[-2000:]))
 d=json.loads(lines[-1]);d['returncode']=r.returncode
 with (out/'airfoil-adaptive.jsonl').open('a') as f:f.write(json.dumps(d)+'\n')
 print(name,d['wall'],d.get('rss_highwater_gib'),d['error'],[e.get('n') for e in d['events'] if e['event']=='factor_init_begin'],flush=True)
