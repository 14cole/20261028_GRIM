"""New tree (49bd93f): automatic policy, explicit backends, production threading."""
import json, subprocess, sys
root, out = sys.argv[1], sys.argv[2]
T = dict(assembly_threads='auto', blas_threads='auto')
auto = dict(entry='solve_monostatic_rcs_2d_certified')
cases = []
def add(mode, **kw):
    opts = dict(T)
    if 'entry' in kw: opts['mesh_strategy'] = 'adaptive'
    cases.append(dict(kw, mode=mode, backend=mode, options=opts))
for b in (dict(body='pec', n=1000), dict(body='diel', n=1000), dict(body='coated', n=2040), dict(body='airfoil', f=1.0),
          dict(body='airfoil', f=1.0, **auto), dict(body='diel', n=1000, **auto), dict(body='pec', n=4000), dict(body='diel', n=2000),
          dict(body='coated', n=4080), dict(body='airfoil', f=3.0), dict(body='airfoil', f=3.0, **auto), dict(body='twobody', n=6000),
          dict(body='diel', n=4000), dict(body='pec', n=8000), dict(body='ibc', n=8000), dict(body='coated', n=6120),
          dict(body='pec', n=10000), dict(body='diel', n=6000), dict(body='pec', n=14000), dict(body='airfoil', f=6.0), dict(body='airfoil', f=10.0)):
    add('automatic', **b)
# explicit choices on the new tree
for b in (dict(body='pec', n=8000), dict(body='coated', n=4080), dict(body='pec', n=4000), dict(body='coated', n=6120), dict(body='airfoil', f=6.0), dict(body='pec', n=14000)):
    add('compressed', **b)
for b in (dict(body='pec', n=10000), dict(body='pec', n=14000), dict(body='pec', n=4000)):
    add('dense', **b)
# automatic under a RAM limit that excludes dense
for b, ram in ((dict(body='pec', n=4000), 0.8), (dict(body='pec', n=8000), 2.0), (dict(body='coated', n=4080), 1.6)):
    c = dict(b, mode='automatic_ram%g' % ram, backend='automatic', options=dict(T, ram_budget_gib=ram)); cases.append(c)
for c in cases:
    try:
        p = subprocess.run([sys.executable, 'case.py', root, json.dumps(c)], capture_output=True, text=True, timeout=3600)
        line = [l for l in p.stdout.splitlines() if l.startswith('{')]
        rec = line[-1] if line else json.dumps(dict(c, error='no output: ' + p.stderr[-300:]))
    except subprocess.TimeoutExpired:
        rec = json.dumps(dict(c, error='timeout'))
    open(out, 'a').write(rec + '\n')
open(out + '.done', 'w').write('done\n')
