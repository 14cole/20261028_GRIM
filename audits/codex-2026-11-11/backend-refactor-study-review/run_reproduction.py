import json, os, subprocess, sys, time
from pathlib import Path
root = sys.argv[1] if len(sys.argv) > 1 else '/workspace/backend-simplification'
out = Path(__file__).resolve().parent / 'results'
out.mkdir(exist_ok=True)
cases=[]
for rep in (1,2):
    variants = [('dense1','dense',1,1,{}),('dense4','dense',4,4,{}),
                ('tile4','compressed',4,4,{}),
                ('h4b1','compressed',4,1,{'GHOST_HMATRIX_MIN_UNKNOWNS':1024}),
                ('h4b4','compressed',4,4,{'GHOST_HMATRIX_MIN_UNKNOWNS':1024})]
    if rep==2: variants.reverse()
    for tag,backend,at,bt,env in variants:
        cases.append((f'pec4000-{tag}-r{rep}',dict(body='pec',n=4000,backend=backend,
            options=dict(assembly_threads=at,blas_threads=bt),env=env)))
for tag,backend,env in [('tile','compressed',{}),('hmatrix','compressed',{'GHOST_HMATRIX_MIN_UNKNOWNS':1024}),('dense','dense',{})]:
    cases.append((f'pec8000-{tag}',dict(body='pec',n=8000,backend=backend,
        options=dict(assembly_threads=4,blas_threads=4),env=env)))
for tag,env in [('hodlr',{}),('lu',{'GHOST_HIERARCHICAL_MIN_UNKNOWNS':1000000})]:
    cases.append((f'pec10000-{tag}',dict(body='pec',n=10000,backend='dense',
        options=dict(assembly_threads=4,blas_threads=4),env=env)))
for tag,spec in cases:
    print('START', tag, flush=True)
    env=dict(os.environ,REVIEW_RESULT_PATH=str(out/tag))
    p=subprocess.run([sys.executable,str(Path(__file__).with_name('case_with_fields.py')),root,json.dumps(spec)],
        env=env,text=True,capture_output=True,timeout=1200)
    (out/(tag+'.stdout')).write_text(p.stdout)
    (out/(tag+'.stderr')).write_text(p.stderr)
    rows=[line for line in p.stdout.splitlines() if line.startswith('{')]
    record=json.loads(rows[-1]) if rows else dict(error='no JSON',stderr=p.stderr[-2000:])
    record.update(tag=tag,process_rc=p.returncode)
    with (out/'timings.jsonl').open('a') as f: f.write(json.dumps(record)+'\n')
    print('DONE',tag,json.dumps({k:record.get(k) for k in ('wall','parent_cpu','peak_tree_gib','error','unknowns','linear_backend')}),flush=True)
