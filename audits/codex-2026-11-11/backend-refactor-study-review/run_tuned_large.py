"""Check whether tuning H-matrix threading changes the proposed crossover."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=sys.argv[1];OUT=Path(__file__).resolve().parent/'results'
for n in (8000,10000):
    tag=f'pec{n}-h4b1'
    spec=dict(body='pec',n=n,backend='compressed',options=dict(assembly_threads=4,blas_threads=1),
              env={'GHOST_HMATRIX_MIN_UNKNOWNS':1024})
    p=subprocess.run([sys.executable,str(Path(__file__).with_name('case_with_fields.py')),ROOT,json.dumps(spec)],
        env=dict(os.environ,REVIEW_RESULT_PATH=str(OUT/tag)),capture_output=True,text=True,timeout=600)
    (OUT/(tag+'.stderr')).write_text(p.stderr)
    lines=[line for line in p.stdout.splitlines() if line.startswith('{')]
    r=json.loads(lines[-1]) if lines else dict(error='no JSON')
    r.update(tag=tag,process_rc=p.returncode)
    with (OUT/'tuned-large.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
    print(json.dumps(r),flush=True)
