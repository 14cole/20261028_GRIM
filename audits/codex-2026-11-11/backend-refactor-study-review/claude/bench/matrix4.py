"""Follow-ups: (a) dense LU with HODLR disabled above 10k unknowns; (b) thread scaling of each backend."""
import json, subprocess, sys
root, out = sys.argv[1], sys.argv[2]
A = dict(assembly_threads='auto', blas_threads='auto')
cases = []
for at in (1, 2, 4):
    for name, extra in (('dense', dict(backend='dense')), ('tile', dict(backend='compressed')), ('hmatrix', dict(backend='compressed', env={'GHOST_HMATRIX_MIN_UNKNOWNS': 1024}))):
        cases.append(dict(body='pec', n=4000, mode=name, tag='threads%d' % at, options=dict(assembly_threads=at, blas_threads=at), **extra))
        cases.append(dict(body='diel', n=2000, mode=name, tag='threads%d' % at, options=dict(assembly_threads=at, blas_threads=at), **extra))
for at, bt in ((4, 1), (1, 4)):
    cases.append(dict(body='pec', n=4000, mode='hmatrix', tag='asm%d_blas%d' % (at, bt), backend='compressed', env={'GHOST_HMATRIX_MIN_UNKNOWNS': 1024}, options=dict(assembly_threads=at, blas_threads=bt)))
    cases.append(dict(body='airfoil', f=6.0, mode='hmatrix', tag='asm%d_blas%d' % (at, bt), backend='compressed', options=dict(assembly_threads=at, blas_threads=bt)))
for b in (dict(body='pec', n=10000), dict(body='diel', n=6000), dict(body='pec', n=14000), dict(body='airfoil', f=6.0)):
    cases.append(dict(b, mode='dense', tag='lu_no_hodlr', backend='dense', env={'GHOST_HIERARCHICAL_MIN_UNKNOWNS': 1000000}, options=A))
for c in cases:
    try:
        p = subprocess.run([sys.executable, 'case.py', root, json.dumps(c)], capture_output=True, text=True, timeout=3600)
        line = [l for l in p.stdout.splitlines() if l.startswith('{')]
        rec = line[-1] if line else json.dumps(dict(c, error='no output: ' + p.stderr[-300:]))
    except subprocess.TimeoutExpired:
        rec = json.dumps(dict(c, error='timeout'))
    open(out, 'a').write(rec + '\n')
open(out + '.done', 'w').write('done\n')
