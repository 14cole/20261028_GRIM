import json, subprocess, sys, os
root, out = sys.argv[1], sys.argv[2]
cases = []
def add(**kw):
    for b in ('dense', 'compressed'): cases.append(dict(kw, backend=b))
for n in (250, 500, 1000, 2000): add(body='pec', n=n)
for n in (500, 1000, 2000): add(body='diel', n=n)
for n in (1020, 2040): add(body='coated', n=n)
for f in (1.0, 3.0): add(body='airfoil', f=f)
add(body='ibc', n=1000); add(body='twobody', n=2000)
# default GUI workflow: automatic mesh search (adaptive, certified)
auto = dict(entry='solve_monostatic_rcs_2d_certified', options=dict(mesh_strategy='adaptive'))
add(body='airfoil', f=1.0, **auto); add(body='pec', n=2000, **auto); add(body='diel', n=1000, **auto)
for n in (4000, 6000): add(body='pec', n=n)
add(body='diel', n=4000); add(body='coated', n=4080); add(body='ibc', n=4000)
add(body='airfoil', f=3.0, **auto)
add(body='airfoil', f=6.0)
add(body='pec', n=8000); add(body='twobody', n=6000); add(body='diel', n=6000); add(body='coated', n=6120)
add(body='pec', n=10000); add(body='ibc', n=8000)
add(body='pec', n=14000); add(body='airfoil', f=10.0)
done = set()
if os.path.exists(out):
    for line in open(out):
        try: d = json.loads(line); done.add(json.dumps({k: d[k] for k in ('body','n','f','backend','entry','options') if k in d}, sort_keys=True))
        except Exception: pass
for c in cases:
    key = json.dumps(c, sort_keys=True)
    if key in done: continue
    try:
        p = subprocess.run([sys.executable, 'case.py', root, json.dumps(c)], capture_output=True, text=True, timeout=3600)
        line = [l for l in p.stdout.splitlines() if l.startswith('{')]
        rec = line[-1] if line else json.dumps(dict(c, error='no output: ' + p.stderr[-300:]))
    except subprocess.TimeoutExpired:
        rec = json.dumps(dict(c, error='timeout 3600 s'))
    open(out, 'a').write(rec + '\n')
open(out + '.done', 'w').write('done\n')
