"""Dense residual storage: memory against disk, production threading."""
import json, subprocess, sys
root, out = sys.argv[1], sys.argv[2]
bodies = [dict(body='pec', n=4000), dict(body='pec', n=8000), dict(body='diel', n=4000), dict(body='coated', n=4080), dict(body='coated', n=6120),
          dict(body='airfoil', f=3.0), dict(body='pec', n=12000), dict(body='pec', n=14000)]
for b in bodies:
    for storage in ('memory', 'disk', 'auto'):
        c = dict(b, storage=storage)
        p = subprocess.run([sys.executable, 'profile_dense.py', root, json.dumps(c)], capture_output=True, text=True, timeout=3600)
        line = [l for l in p.stdout.splitlines() if l.startswith('{')]
        open(out, 'a').write((line[-1] if line else json.dumps(dict(c, error='no output: '+p.stderr[-300:]))) + '\n')
open(out+'.done', 'w').write('done\n')
