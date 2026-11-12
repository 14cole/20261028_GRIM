import json, subprocess, sys
root, out = sys.argv[1], sys.argv[2]
C = []
for th in (1, 2, 4):
    C.append(dict(body='pec', n=8000, mode='compressed', threads=th, tag='pec8000-compressed-t%d' % th))
    C.append(dict(body='pec', n=8000, mode='dense', threads=th, tag='pec8000-dense-t%d' % th))
for th in (1, 4):
    C.append(dict(body='coated', n=4080, mode='compressed', threads=th, tag='coated6480-compressed-t%d' % th))
    C.append(dict(body='coated', n=4080, mode='dense', threads=th, tag='coated6480-dense-t%d' % th))
    C.append(dict(body='diel', n=4000, mode='compressed', threads=th, tag='diel8000-compressed-t%d' % th))
C.append(dict(body='airfoil', f=6.0, mode='compressed', threads=4, tag='airfoil17120-compressed-t4'))
C.append(dict(body='pec', n=14000, mode='compressed', threads=4, tag='pec14000-compressed-t4'))
# equal electrical size at two physical scales
for radius in (1.0, 0.05):
    for mode in ('dense', 'compressed'):
        C.append(dict(body='diel', n=2000, mode=mode, radius=radius, threads=4, angles=19, sample=False, tag='scale-r%g-%s' % (radius, mode), out='scale-r%g-%s.npy' % (radius, mode)))
        C.append(dict(body='coated', n=2040, mode=mode, radius=radius, threads=4, angles=19, sample=False, tag='scalecoat-r%g-%s' % (radius, mode), out='scalecoat-r%g-%s.npy' % (radius, mode)))
for c in C:
    p = subprocess.run([sys.executable, 'sample_solve.py', root, json.dumps(c)], capture_output=True, text=True, timeout=3600)
    line = [l for l in p.stdout.splitlines() if l.startswith('{')]
    open(out, 'a').write((line[-1] if line else json.dumps(dict(c, error='no output: '+p.stderr[-400:]))) + '\n')
open(out+'.done', 'w').write('done\n')
