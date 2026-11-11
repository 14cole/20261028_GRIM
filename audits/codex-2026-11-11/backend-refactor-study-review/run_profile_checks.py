"""Recheck two measured cases with the complete automatic profile used by the GUI."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(sys.argv[1]);OUT=Path(__file__).resolve().parent/'results'
sys.path.insert(0,str(ROOT/'tools/GHOST'))
from ghost_backend.execution.options import automatic_options
for n in (4000,8000):
    opts=automatic_options()
    opts.update(assembly_threads=4,blas_threads=4)
    tag=f'pec{n}-gui-profile'
    spec=dict(body='pec',n=n,backend='compressed',options=opts)
    env=dict(os.environ,REVIEW_RESULT_PATH=str(OUT/tag))
    p=subprocess.run([sys.executable,str(Path(__file__).with_name('case_with_fields.py')),str(ROOT),json.dumps(spec)],env=env,capture_output=True,text=True,timeout=600)
    (OUT/(tag+'.stderr')).write_text(p.stderr)
    rows=[line for line in p.stdout.splitlines() if line.startswith('{')]
    r=json.loads(rows[-1]) if rows else dict(error='no JSON')
    r.update(tag=tag,process_rc=p.returncode)
    with (OUT/'profile-checks.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
    print(json.dumps(r),flush=True)
