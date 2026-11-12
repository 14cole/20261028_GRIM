"""Fresh-process reproductions of the conservative floor and rounded refusal."""
import json,os,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve();p=Path(__file__).resolve().parent
profiler=root/'audits/codex-2026-11-12/dense-memory-implementation/profile_solve.py'
wrapper=root/'audits/codex-2026-11-12/dense-memory-implementation/allocation_wrapper.py'
env={k:v for k,v in os.environ.items() if not k.startswith('GHOST_')};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
cases=[dict(case='diel-memory-4g',body='diel',n=4000,storage='memory',options=dict(ram_budget_gib=4.)),
       dict(case='diel-refused-1.6g',body='diel',n=4000,options=dict(ram_budget_gib=1.6)),
       dict(case='diel-disk-2.4g',body='diel',n=4000,storage='disk',options=dict(ram_budget_gib=2.4)),
       dict(case='pec-rounded-refusal',body='pec',n=8000,options=dict(ram_budget_gib=1.5))]
for c in cases:
 if len(sys.argv)>2 and c['case'] not in sys.argv[2:]:continue
 spec=dict(c,allocation_cpus=4,out=str(p/'results'/(c['case']+'.npz')))
 r=subprocess.run([sys.executable,str(wrapper),str(root),str(profiler),json.dumps(spec)],capture_output=True,text=True,env=env,timeout=300)
 (p/'results'/(c['case']+'.log')).write_text(r.stderr)
 rows=[x for x in r.stdout.splitlines() if x.startswith('{')];assert rows,(r.returncode,r.stderr)
 d=json.loads(rows[-1]);(p/'results'/(c['case']+'.json')).write_text(json.dumps(d,indent=2)+'\n')
 assert (d['error'] is None)==(c['case'] in ('diel-disk-2.4g','diel-memory-4g')),d
 print(c['case'],d['wall'],d['peak_gib'],d['error'],flush=True)
