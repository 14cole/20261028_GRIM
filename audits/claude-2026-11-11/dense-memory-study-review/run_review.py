"""Independent checks of Codex's dense-memory review claims on d162169."""
import json, subprocess, sys
root, out, bench = sys.argv[1], sys.argv[2], sys.argv[3]
T = dict(assembly_threads='auto', blas_threads='auto')
def prof(spec):
    p = subprocess.run([sys.executable, 'profile_dense.py', root, json.dumps(spec)], capture_output=True, text=True, timeout=3600)
    line = [l for l in p.stdout.splitlines() if l.startswith('{')]
    open(out, 'a').write((line[-1] if line else json.dumps(dict(spec, error='no output: '+p.stderr[-300:]))) + '\n')
def case(spec):
    p = subprocess.run([sys.executable, bench+'/case.py', root, json.dumps(spec)], capture_output=True, text=True, timeout=3600, cwd=bench)
    line = [l for l in p.stdout.splitlines() if l.startswith('{')]
    open(out, 'a').write((line[-1] if line else json.dumps(dict(spec, error='no output: '+p.stderr[-300:]))) + '\n')
# lean dense against compressed where Codex reports compressed ahead
for rep in (0, 1):
    case(dict(body='airfoil', f=3.0, backend='compressed', tag='airfoil-compressed', options=T))
    prof(dict(body='airfoil', f=3.0, storage='disk', tag='airfoil-lean', options=dict(ram_budget_gib=3.3)))
    case(dict(body='pec', n=14000, backend='compressed', tag='pec14000-compressed', options=T))
    case(dict(body='coated', n=6120, backend='compressed', tag='coated-compressed-2.4', options=dict(T, ram_budget_gib=2.4)))
# further savings above lean dense: smaller angle batch and assembly tile
for body, ram in ((dict(body='pec', n=8000), 3.0), (dict(body='coated', n=6120), 4.2)):
    for tag, extra in (('lean', {}), ('lean-batch64', dict(angle_batch_size=64)), ('lean-tile128', dict(assembly_tile=128)),
                       ('lean-batch64-tile128', dict(angle_batch_size=64, assembly_tile=128))):
        prof(dict(body, storage='disk', tag=tag, out='rev_%s_%s.npz' % (body['body'], tag), options=dict(ram_budget_gib=ram, **extra)))
open(out+'.done', 'w').write('done\n')
