"""Dense under a tightening RAM budget: pairing, automatic spooling, admission; and what Automatic selects."""
import json, subprocess, sys
root, out = sys.argv[1], sys.argv[2]
cases = []
for b, budgets in ((dict(body='pec', n=8000), (None, 3.0, 2.4, 2.0, 1.7, 1.4, 1.2)), (dict(body='coated', n=6120), (None, 4.2, 3.4, 2.8, 2.2, 1.9)),
                   (dict(body='diel', n=4000), (None, 2.0, 1.6, 1.3)), (dict(body='pec', n=14000), (8.5, 7.0, 5.5, 4.5, 3.8))):
    for ram in budgets:
        for mode in ('dense', 'automatic'):
            if ram is None and mode == 'automatic': continue
            cases.append(dict(b, mode=mode, ram=ram, options=dict(ram_budget_gib=ram)))
for c in cases:
    p = subprocess.run([sys.executable, 'profile_dense.py', root, json.dumps(c)], capture_output=True, text=True, timeout=3600)
    line = [l for l in p.stdout.splitlines() if l.startswith('{')]
    open(out, 'a').write((line[-1] if line else json.dumps(dict(c, error='no output: '+p.stderr[-300:]))) + '\n')
open(out+'.done', 'w').write('done\n')
