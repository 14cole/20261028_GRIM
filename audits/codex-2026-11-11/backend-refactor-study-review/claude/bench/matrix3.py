"""Production threading (assembly_threads='auto', blas_threads='auto'): dense, compressed, compressed with H-matrix from 1024 unknowns."""
import json, subprocess, sys, os
root, out = sys.argv[1], sys.argv[2]
T = dict(assembly_threads='auto', blas_threads='auto')
modes = [('dense', dict(backend='dense')), ('compressed', dict(backend='compressed')),
         ('hmatrix1024', dict(backend='compressed', env={'GHOST_HMATRIX_MIN_UNKNOWNS': 1024}))]
bodies = []
def add(**kw): bodies.append(kw)
auto = dict(entry='solve_monostatic_rcs_2d_certified')
for n in (500, 1000, 2000): add(body='pec', n=n)
add(body='diel', n=500); add(body='diel', n=1000); add(body='coated', n=1020); add(body='coated', n=2040)
add(body='airfoil', f=1.0); add(body='ibc', n=1000); add(body='twobody', n=2000)
add(body='airfoil', f=1.0, **auto); add(body='pec', n=2000, **auto); add(body='diel', n=1000, **auto)
add(body='pec', n=4000); add(body='diel', n=2000); add(body='ibc', n=4000); add(body='coated', n=4080)
add(body='airfoil', f=3.0); add(body='airfoil', f=3.0, **auto)
add(body='pec', n=6000); add(body='twobody', n=6000); add(body='diel', n=4000)
add(body='pec', n=8000); add(body='ibc', n=8000); add(body='coated', n=6120); add(body='diel', n=6000)
add(body='pec', n=10000); add(body='airfoil', f=6.0); add(body='pec', n=14000); add(body='airfoil', f=10.0)
for b in bodies:
    for name, extra in modes:
        opts = dict(T)
        if 'entry' in b: opts['mesh_strategy'] = 'adaptive'
        c = dict(b, mode=name, options=opts, **extra)
        if name == 'dense' and b.get('f') == 10.0: continue
        try:
            p = subprocess.run([sys.executable, 'case.py', root, json.dumps(c)], capture_output=True, text=True, timeout=3600)
            line = [l for l in p.stdout.splitlines() if l.startswith('{')]
            rec = line[-1] if line else json.dumps(dict(c, error='no output: ' + p.stderr[-300:]))
        except subprocess.TimeoutExpired:
            rec = json.dumps(dict(c, error='timeout'))
        open(out, 'a').write(rec + '\n')
open(out + '.done', 'w').write('done\n')
