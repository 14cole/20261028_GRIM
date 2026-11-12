"""Scenario checks of the dense-memory implementation (ae08d66) with my profiler."""
import json, subprocess, sys
root, out, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
cases = [
 dict(body='pec', n=8000, tag='pec8000-default'),
 dict(body='pec', n=8000, tag='pec8000-dense-2.0', options=dict(ram_budget_gib=2.0)),
 dict(body='pec', n=8000, tag='pec8000-dense-1.5', options=dict(ram_budget_gib=1.5)),
 dict(body='pec', n=8000, tag='pec8000-auto-2.0', mode='automatic', options=dict(ram_budget_gib=2.0)),
 dict(body='coated', n=6120, tag='coated-default'),
 dict(body='coated', n=6120, tag='coated-disk', storage='disk'),
 dict(body='coated', n=6120, tag='coated-dense-2.0', options=dict(ram_budget_gib=2.0)),
 dict(body='coated', n=6120, tag='coated-auto-2.0', mode='automatic', options=dict(ram_budget_gib=2.0)),
 dict(body='coated', n=6120, tag='coated-auto-2.8', mode='automatic', options=dict(ram_budget_gib=2.8)),
 dict(body='coated', n=6120, tag='coated-compressed-2.8', mode='compressed', options=dict(ram_budget_gib=2.8)),
 dict(body='coated', n=6120, tag='coated-compressed-1.9', mode='compressed', options=dict(ram_budget_gib=1.9)),
 dict(body='diel', n=4000, tag='diel-default'),
 dict(body='diel', n=4000, tag='diel-dense-1.6', options=dict(ram_budget_gib=1.6)),
 dict(body='airfoil', f=3.0, tag='airfoil-default'),
 dict(body='airfoil', f=3.0, tag='airfoil-dense-2.0', options=dict(ram_budget_gib=2.0)),
 dict(body='pec', n=14000, tag='pec14000-disk', storage='disk'),
 dict(body='pec', n=14000, tag='pec14000-dense-5.5', options=dict(ram_budget_gib=5.5)),
 dict(body='pec', n=14000, tag='pec14000-auto-5.5', mode='automatic', options=dict(ram_budget_gib=5.5)),
]
for c in cases:
    c['out'] = '%s/%s.npz' % (outdir, c['tag'])
    p = subprocess.run([sys.executable, 'profile_dense.py', root, json.dumps(c)], capture_output=True, text=True, timeout=3600)
    line = [l for l in p.stdout.splitlines() if l.startswith('{')]
    open(out, 'a').write((line[-1] if line else json.dumps(dict(c, error='no output: '+p.stderr[-400:]))) + '\n')
open(out+'.done', 'w').write('done\n')
