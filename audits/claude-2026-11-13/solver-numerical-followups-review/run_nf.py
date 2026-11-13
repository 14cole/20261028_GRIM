"""Before/after checks of ee66611 against 965d941."""
import json, subprocess, sys
old, new, out, fields = sys.argv[1:5]
def run(root, spec):
    p = subprocess.run([sys.executable, 'sample_solve.py', root, json.dumps(spec)], capture_output=True, text=True, timeout=3600)
    line = [l for l in p.stdout.splitlines() if l.startswith('{')]
    open(out, 'a').write((line[-1] if line else json.dumps(dict(spec, error='no output: '+p.stderr[-400:]))) + '\n')
T = (('old', old), ('new', new))
# 1. Dense: time, memory and field change, in memory and with disk residuals; two alternating repeats
for rep in (0, 1):
    for body, key in (('pec', dict(n=8000)), ('diel', dict(n=4000)), ('coated', dict(n=4080)), ('airfoil', dict(f=3.0))):
        for name, root in T:
            base = '%s%s' % (body, key.get('n', 'f3'))
            run(root, dict(body=body, mode='dense', sample=False, tree=name, tag='dense-%s-%s-%d' % (base, name, rep), out='%s/dense-%s-%s-%d.npy' % (fields, base, name, rep), **key))
            if rep == 0:
                run(root, dict(body=body, mode='dense', sample=False, tree=name, tag='densedisk-%s-%s' % (base, name), options=dict(dense_residual_storage='disk'), out='%s/densedisk-%s-%s.npy' % (fields, base, name), **key))
# 2. Compressed dielectric and others; three alternating repeats for the dielectric
for rep in (0, 1, 2):
    for name, root in T:
        run(root, dict(body='diel', n=4000, mode='compressed', sample=False, tree=name, tag='comp-diel4000-%s-%d' % (name, rep), out='%s/comp-diel4000-%s-%d.npy' % (fields, name, rep)))
for body, key in (('pec', dict(n=8000)), ('coated', dict(n=4080)), ('airfoil', dict(f=3.0)), ('diel', dict(n=1500)), ('diel', dict(n=6000))):
    for name, root in T:
        base = '%s%s' % (body, key.get('n', 'f3'))
        run(root, dict(body=body, mode='compressed', sample=False, tree=name, tag='comp-%s-%s' % (base, name), out='%s/comp-%s-%s.npy' % (fields, base, name), **key))
# 3. scale scan: Dense and hierarchical on the coated and dielectric bodies; legacy tiles on a small dielectric
for body, n in (('coated', 2040), ('diel', 2000)):
    for radius in (100, 1, 0.01):
        for name, root in T:
            for mode in ('dense', 'compressed'):
                run(root, dict(body=body, n=n, mode=mode, radius=radius, angles=19, sample=False, tree=name, tag='scale-%s-r%g-%s-%s' % (body, radius, mode, name), out='%s/scale-%s-r%g-%s-%s.npy' % (fields, body, radius, mode, name)))
for radius in (100, 0.01):
    for name, root in T:
        for mode in ('dense', 'compressed'):
            run(root, dict(body='diel', n=400, mode=mode, radius=radius, angles=19, sample=False, tree=name, tag='tile-diel-r%g-%s-%s' % (radius, mode, name), out='%s/tile-diel-r%g-%s-%s.npy' % (fields, radius, mode, name)))
open(out+'.done', 'w').write('done\n')
