"""Scenario checks of the backend stress improvements (cfe005a) with my profiler."""
import json, subprocess, sys
root, out, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
C = []
def add(tag, **kw): C.append(dict(kw, tag=tag))
for body, key in (('pec', dict(n=2000)), ('pec', dict(n=3000)), ('pec', dict(n=8000)), ('diel', dict(n=2000)), ('diel', dict(n=4000)),
                  ('coated', dict(n=4080)), ('coated', dict(n=6120)), ('airfoil', dict(f=3.0))):
    name = '%s%s' % (body, key.get('n', 'f3'))
    add(name+'-dense', body=body, **key)
    add(name+'-compressed', body=body, mode='compressed', **key)
add('coated6120-compressed-2.8', body='coated', n=6120, mode='compressed', options=dict(ram_budget_gib=2.8))
add('coated6120-compressed-2.4', body='coated', n=6120, mode='compressed', options=dict(ram_budget_gib=2.4))
add('coated6120-compressed-1.9', body='coated', n=6120, mode='compressed', options=dict(ram_budget_gib=1.9))
add('pec8000-compressed-override8192', body='pec', n=8000, mode='compressed', env={'GHOST_HMATRIX_MIN_UNKNOWNS': '8192'})
add('diel4000-dense-disk-1.8', body='diel', n=4000, storage='disk', options=dict(ram_budget_gib=1.8))
add('diel4000-dense-auto-1.8', body='diel', n=4000, options=dict(ram_budget_gib=1.8))
add('diel4000-dense-memory-1.8', body='diel', n=4000, storage='memory', options=dict(ram_budget_gib=1.8))
add('diel4000-dense-disk-1.6', body='diel', n=4000, storage='disk', options=dict(ram_budget_gib=1.6))
add('diel4000-automatic-1.8', body='diel', n=4000, mode='automatic', options=dict(ram_budget_gib=1.8))
add('diel4000-automatic-2.3', body='diel', n=4000, mode='automatic', options=dict(ram_budget_gib=2.3))
add('pec14000-compressed', body='pec', n=14000, mode='compressed')
for c in C:
    c['out'] = '%s/%s.npz' % (outdir, c['tag'])
    env = dict(__import__('os').environ, **c.pop('env', {}))
    p = subprocess.run([sys.executable, 'profile_dense.py', root, json.dumps(c)], capture_output=True, text=True, timeout=3600, env=env)
    line = [l for l in p.stdout.splitlines() if l.startswith('{')]
    open(out, 'a').write((line[-1] if line else json.dumps(dict(c, error='no output: '+p.stderr[-400:]))) + '\n')
open(out+'.done', 'w').write('done\n')
