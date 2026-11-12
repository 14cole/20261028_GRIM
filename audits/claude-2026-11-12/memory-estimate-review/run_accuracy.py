import json, subprocess, sys
root, out = sys.argv[1], sys.argv[2]
cases = []
for body, sizes in (('pec', (4000, 8000)), ('ibc', (4000, 8000)), ('diel', (2000, 4000)), ('coated', (4080, 6120)), ('twobody', (4000, 8000))):
    for n in sizes:
        cases.append(dict(body=body, n=n, tag='default')); cases.append(dict(body=body, n=n, tag='disk', storage='disk'))
for f in (1.0, 3.0):
    cases.append(dict(body='airfoil', f=f, tag='default')); cases.append(dict(body='airfoil', f=f, tag='disk', storage='disk'))
for body, n in (('pec', 8000), ('diel', 4000), ('coated', 6120)):
    cases.append(dict(body=body, n=n, tag='default-1thread', threads=1)); cases.append(dict(body=body, n=n, tag='disk-1thread', storage='disk', threads=1))
# tight budgets: plan constrained (batch reduction, tile 128)
for body, n, ram in (('pec', 8000, 1.6), ('coated', 6120, 2.0), ('airfoil', None, 1.7), ('twobody', 8000, 1.6), ('ibc', 8000, 1.6)):
    c = dict(body=body, tag='budget-%g' % ram, options=dict(ram_budget_gib=ram)); c.update(dict(f=3.0) if body == 'airfoil' else dict(n=n)); cases.append(c)
# higher order on a fixed mesh
for body, n, deg in (('pec', 2000, 2), ('pec', 2000, 3), ('diel', 1000, 2), ('coated', 2040, 2)):
    cases.append(dict(body=body, n=n, tag='P%d' % deg, options=dict(basis_order=deg, mesh_strategy='global')))
for c in cases:
    p = subprocess.run([sys.executable, 'forecast_accuracy.py', root, json.dumps(c)], capture_output=True, text=True, timeout=3600)
    line = [l for l in p.stdout.splitlines() if l.startswith('{')]
    open(out, 'a').write((line[-1] if line else json.dumps(dict(c, error='no output: '+p.stderr[-400:]))) + '\n')
open(out+'.done', 'w').write('done\n')
