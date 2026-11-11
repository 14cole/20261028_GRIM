"""Explain small forward-field differences without changing acceptance thresholds."""
import os,sys,json,subprocess
from pathlib import Path
p=Path(__file__).parent;root=sys.argv[1];out=Path(sys.argv[2]) if len(sys.argv)>2 else p
(out/'fingerprints').mkdir(exist_ok=True,parents=True)
env={k:v for k,v in os.environ.items() if not k.startswith('GHOST_')};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
for variant in ('baseline','batch64','combined'):
 spec=dict(case=variant,body='coated',n=6120,threads=4,storage='disk',force_unpaired=True,fingerprint=True,options=dict(ram_budget_gib=4.2,angle_batch_size=256 if variant=='baseline' else 64),out=str(out/'fingerprints'/(variant+'.npz')))
 if variant=='combined':spec['options']['assembly_tile']=128;spec['bounded_spool']=True
 r=subprocess.run([sys.executable,str(p/'profile_opportunities.py'),root,json.dumps(spec)],capture_output=True,text=True,env=env,timeout=900)
 (out/'fingerprints'/(variant+'.stderr')).write_text(r.stderr)
 lines=[x for x in r.stdout.splitlines() if x.startswith('{')]
 if not lines:raise RuntimeError(r.stderr[-2000:])
 d=json.loads(lines[-1])
 with (out/'fingerprints.jsonl').open('a') as file:file.write(json.dumps(d)+'\n')
 print(variant,d['error'],d['fingerprints'],flush=True)
