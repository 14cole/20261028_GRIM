import json, subprocess, sys, os
root, out = sys.argv[1], sys.argv[2]
env = {'GHOST_HMATRIX_MIN_UNKNOWNS': 1024}
cases = [dict(body='pec', n=2000), dict(body='diel', n=1000), dict(body='coated', n=2040), dict(body='airfoil', f=1.0),
         dict(body='diel', n=2000), dict(body='pec', n=4000), dict(body='ibc', n=4000), dict(body='coated', n=4080),
         dict(body='airfoil', f=3.0, entry='solve_monostatic_rcs_2d_certified', options=dict(mesh_strategy='adaptive')),
         dict(body='pec', n=6000), dict(body='twobody', n=6000), dict(body='pec', n=8000), dict(body='ibc', n=8000), dict(body='diel', n=4000),
         dict(body='pec', n=1000), dict(body='twobody', n=2000)]
for c in cases:
    c = dict(c, backend='compressed', env=env)
    try:
        p = subprocess.run([sys.executable, 'case.py', root, json.dumps(c)], capture_output=True, text=True, timeout=3600)
        line = [l for l in p.stdout.splitlines() if l.startswith('{')]
        rec = line[-1] if line else json.dumps(dict(c, error='no output: ' + p.stderr[-300:]))
    except subprocess.TimeoutExpired:
        rec = json.dumps(dict(c, error='timeout'))
    open(out, 'a').write(rec + '\n')
open(out + '.done', 'w').write('done\n')
