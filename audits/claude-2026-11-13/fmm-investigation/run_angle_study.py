import json, os, subprocess, sys
out = sys.argv[1]
def run(spec, blas='1'):
    env = dict(os.environ, OPENBLAS_NUM_THREADS=blas, OMP_NUM_THREADS=blas)
    p = subprocess.run([sys.executable, 'angle_study.py', json.dumps(spec)], capture_output=True, text=True, env=env, timeout=7200)
    line = [l for l in p.stdout.splitlines() if l.startswith('{')]
    open(out, 'a').write((line[-1] if line else json.dumps(dict(spec, error=p.stderr[-400:]))) + '\n')
base = dict(kind='star', ka=640, ppw=12, angles=61)
run(dict(base, strategy='batch', batch=1, angles=8, tag='one-at-a-time (8 angles only)'))
for b in (8, 32, 61):
    run(dict(base, strategy='batch', batch=b, tag='batch%d' % b, out='sig-batch%d.npy' % b))
run(dict(base, strategy='batch', batch=61, tag='batch61-blas4'), blas='4')
for w in (2, 4):
    run(dict(base, strategy='threads', batch=8, workers=w, tag='threads%d' % w, out='sig-threads%d.npy' % w))
    run(dict(base, strategy='processes', batch=8, workers=w, tag='processes%d' % w, out='sig-processes%d.npy' % w))
run(dict(base, strategy='warm', batch=8, tag='warm8', out='sig-warm8.npy'))
run(dict(base, strategy='compressed', batch=32, tag='compressed', out='sig-compressed.npy'))
# RHS rank against angular sampling density and electrical size
for ka, m in ((160, 181), (160, 721), (640, 181), (640, 721), (640, 1801)):
    run(dict(kind='star', ka=ka, ppw=12, angles=m, strategy='compressed', batch=32, processes=1, tag='rank-ka%d-m%d' % (ka, m), rank_only=True, tol=1e-8))
# other geometry, and a full-scale 181-angle run with four processes
run(dict(kind='cavity', ka=640, ppw=12, angles=61, strategy='processes', batch=8, workers=4, tag='cavity-processes4', out='sig-cavity.npy'))
run(dict(kind='circle', ka=640, ppw=12, angles=61, strategy='processes', batch=8, workers=4, tag='circle-processes4', out='sig-circle.npy'))
run(dict(kind='star', ka=1150, ppw=12, angles=181, strategy='processes', batch=8, workers=4, tag='star-ka1150-181-processes4', out='sig-star1150.npy'))
run(dict(kind='star', ka=1150, ppw=20, angles=16, strategy='processes', batch=4, workers=4, tag='star-ka1150-ppw20-16angles', out='sig-star1150-ppw20.npy'))
open(out + '.done', 'w').write('done\n')
