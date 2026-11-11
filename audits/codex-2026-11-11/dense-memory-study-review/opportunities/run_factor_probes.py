import sys,os,json,subprocess
from pathlib import Path
import numpy as np
p=Path(__file__).parent;root=sys.argv[1];out=Path(sys.argv[2]) if len(sys.argv)>2 else p
art=out/'factors';art.mkdir(parents=True,exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith('GHOST_')};env.update(OPENBLAS_NUM_THREADS='4',OMP_NUM_THREADS='4')
cases=[dict(case='pec',body='pec',n=4000),dict(case='coated',body='coated',n=680),dict(case='dielectric',body='diel',n=512)]
records=[]
for c in ([] if len(sys.argv)>3 and sys.argv[3]=='reuse' else cases):
 spec=dict(c,threads=4,angles=7,storage='disk',capture_directory=str(art),out=str(art/(c['case']+'-fields.npz')))
 r=subprocess.run([sys.executable,str(p/'capture_matrices.py'),root,str(p/'profile_opportunities.py'),json.dumps(spec)],env=env,capture_output=True,text=True,timeout=300)
 (art/(c['case']+'-capture.log')).write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(r.stderr[-2000:])
 records+=json.loads((art/(c['case']+'-capture.json')).read_text())
if len(sys.argv)>3 and sys.argv[3]=='reuse':records=json.loads((out/'matrix-fixtures.json').read_text())[:-1]
# Difficult synthetic matrix exercises rejection rather than promising universal mixed convergence.
rng=np.random.default_rng(20261111);q,_=np.linalg.qr(rng.normal(size=(64,64))+1j*rng.normal(size=(64,64)))
a=np.asarray((q*np.geomspace(1.,1e-12,64))@q.conj().T,complex);prefix=str(art/'ill-conditioned')
a.tofile(prefix+'-matrix.raw');Path(prefix+'-info.json').write_text(json.dumps(dict(n=64)))
np.save(prefix+'-rhs.npy',rng.normal(size=(64,3))+1j*rng.normal(size=(64,3)))
records.append(dict(case='ill-conditioned',n=64,prefix=prefix,nominal_condition=1e12))
(out/'matrix-fixtures.json').write_text(json.dumps(records,indent=2)+'\n')
for c in records:
 for method in ('double-spool','mixed-memory','mixed-spool'):
  r=subprocess.run([sys.executable,str(p/'factor_probe.py'),root,c['prefix'],method],env=env,capture_output=True,text=True,timeout=300)
  (art/(Path(c['prefix']).name+'-'+method+'.stderr')).write_text(r.stderr)
  if r.returncode:raise RuntimeError(r.stderr[-2000:])
  d=json.loads(r.stdout.strip().splitlines()[-1])
  if not d['error'] and method!='double-spool':
   for row in d['results']:
    ref=np.load(c['prefix']+'-double-spool-t'+str(row['trans'])+'.npy');x=np.load(c['prefix']+'-'+method+'-t'+str(row['trans'])+'.npy')
    row['relative_solution_difference']=float(np.max(abs(x-ref))/np.max(abs(ref)))
  with (out/'factor-probes.jsonl').open('a') as f:f.write(json.dumps(d)+'\n')
  print(c['case'],c.get('index'),method,d['error'],flush=True)
