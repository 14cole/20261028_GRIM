"""Two fresh processes running Claude's pinned harness without modifications."""
import os,sys,json,time,subprocess
from pathlib import Path
R=Path(__file__).resolve().parent
roots={'original':os.environ['BASE_GRIM_ROOT'],'fixed':os.environ['GRIM_ROOT']}
(R/'results').mkdir(exist_ok=True)
for variant,root in roots.items():
    out=R/'results'/variant
    if out.with_suffix('.time.json').exists():raise RuntimeError('Refusing overwrite')
    spec=dict(n=512,kind='slot',k=10,out=str(out))
    env=dict(os.environ,GRIM_ROOT=root,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    t=time.perf_counter()
    with out.with_suffix('.stdout').open('w') as o,out.with_suffix('.stderr').open('w') as e:
        p=subprocess.run([sys.executable,str(R/'claude/claude_lifecycle.py'),json.dumps(spec)],env=env,stdout=o,stderr=e)
    out.with_suffix('.time.json').write_text(json.dumps(dict(returncode=p.returncode,wall_seconds=time.perf_counter()-t)))
    print(variant,p.returncode,flush=True)
    if p.returncode:raise SystemExit(p.returncode)
