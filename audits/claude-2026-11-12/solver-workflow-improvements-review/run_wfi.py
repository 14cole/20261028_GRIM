"""Before/after checks of 965d941 against cfe005a: scale scan, timing by stage, Automatic lean plan."""
import json, subprocess, sys
old, new, out, fields = sys.argv[1:5]
def run(root, spec):
    p = subprocess.run([sys.executable, 'sample_solve.py', root, json.dumps(spec)], capture_output=True, text=True, timeout=3600)
    line = [l for l in p.stdout.splitlines() if l.startswith('{')]
    open(out, 'a').write((line[-1] if line else json.dumps(dict(spec, error='no output: '+p.stderr[-400:]))) + '\n')
# 1. scale scan on the new tree (dense references are scale-specific)
for body, n in (('diel', 2000), ('coated', 2040), ('pec', 4000)):
    for radius in (100, 1, 0.05, 0.01):
        for mode in ('dense', 'compressed'):
            run(new, dict(body=body, n=n, mode=mode, radius=radius, angles=19, sample=False, tree='new', tag='scale-%s-r%g-%s' % (body, radius, mode), out='%s/scale-%s-r%g-%s.npy' % (fields, body, radius, mode)))
# 2. timing, alternating old and new, two repeats, default threads, sampler off
for rep in (0, 1):
    for body, key in (('pec', dict(n=8000)), ('diel', dict(n=4000)), ('coated', dict(n=4080)), ('airfoil', dict(f=6.0)), ('airfoil', dict(f=3.0))):
        for name, root in (('old', old), ('new', new)):
            tag = 'time-%s%s-%s-%d' % (body, key.get('n', 'f%g' % key.get('f', 0)), name, rep)
            run(root, dict(body=body, mode='compressed', sample=False, tree=name, tag=tag, out='%s/%s.npy' % (fields, tag), **key))
# dense references for the timing bodies
for body, key in (('pec', dict(n=8000)), ('diel', dict(n=4000)), ('coated', dict(n=4080)), ('airfoil', dict(f=3.0))):
    tag = 'ref-%s%s-dense' % (body, key.get('n', 'f%g' % key.get('f', 0)))
    run(new, dict(body=body, mode='dense', sample=False, tree='new', tag=tag, out='%s/%s.npy' % (fields, tag), **key))
# 3. numeric BLAS cap no longer hurts
for name, root in (('old', old), ('new', new)):
    run(root, dict(body='pec', n=8000, mode='compressed', threads=4, sample=False, tree=name, tag='blas4-pec8000-%s' % name))
# 4. Automatic lean Dense
for ram in (2.3, 2.6, 3.2):
    for name, root in (('old', old), ('new', new)):
        run(root, dict(body='diel', n=4000, mode='automatic', sample=False, tree=name, tag='auto-diel8000-%g-%s' % (ram, name), options=dict(ram_budget_gib=ram), out='%s/auto-diel8000-%g-%s.npy' % (fields, ram, name)))
open(out+'.done', 'w').write('done\n')
