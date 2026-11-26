"""For each degraded-native state: fresh export of tools/GHOST at ed90b65, mutate, run the shipped diagnostic and solve_probe.py.

usage: degraded_native_states.py GRIM_CHECKOUT WORKDIR OUT.json
"""
import io, json, os, shutil, subprocess, sys, tarfile
from pathlib import Path
import numpy as np
COMMIT = 'ed90b65ff89826274adacae01bcfbafe143e9819'
repo, work, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
here = Path(__file__).resolve().parent
shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
tar = subprocess.run(['git', '-C', str(repo), 'archive', COMMIT, 'tools/GHOST'], check=True, capture_output=True).stdout
N = 'ghost_backend/twod/assembly/native/'

def stub(path, source):
    c = path.with_suffix('.stub.c'); c.write_text(source)
    subprocess.run(['gcc', '-shared', '-fPIC', '-O1', '-o', str(path), str(c)], check=True); c.unlink()

STATES = {
    'a_baseline': lambda g: None,
    'b_near_missing': lambda g: (g/N/'libghost_near.so').unlink(),
    'c_near_truncated': lambda g: (g/N/'libghost_near.so').write_bytes((g/N/'libghost_near.so').read_bytes()[:1000]),
    'c2_near_garbage': lambda g: (g/N/'libghost_near.so').write_bytes(b'not an ELF file\n'*64),
    'd_near_wrong_exports': lambda g: stub(g/N/'libghost_near.so', 'int unrelated(void){return 0;}\n'),
    'd2_near_one_export_short': lambda g: stub(g/N/'libghost_near.so', ''.join(
        f'int {n}(void){{return 1;}}\n' for n in ('ghost_near_box_arguments', 'ghost_near_box_blocks', 'ghost_thin_analytic',
                                                 'ghost_thin_squares', 'ghost_thin_remainder', 'ghost_near_has_fused'))),
    'e_far_wrong_exports': lambda g: stub(g/N/'libghost_far.so', 'int unrelated(void){return 0;}\n'),
    'e2_far_missing': lambda g: (g/N/'libghost_far.so').unlink(),
    'f_table_wrong_exports': lambda g: stub(g/N/'libghost_table.so', 'int unrelated(void){return 0;}\n'),
    'g_all_three_2d_missing': lambda g: [(g/N/f'libghost_{n}.so').unlink() for n in ('near', 'far', 'table')],
}
report, base = {}, None
for name, mutate in STATES.items():
    root = work/name; root.mkdir()
    tarfile.open(fileobj=io.BytesIO(tar)).extractall(root, filter='data')
    ghost = root/'tools/GHOST'; mutate(ghost)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('OPENBLAS', 'OMP_', 'MKL', 'GHOST', 'PYTHONPATH'))}
    d = subprocess.run([sys.executable, '-W', 'always', str(ghost/'scripts/check_speed_paths.py')], capture_output=True, text=True, env=env)
    rows = [l for l in d.stdout.splitlines()[1:]]
    env['PYTHONPATH'] = str(ghost)
    s = subprocess.run([sys.executable, '-W', 'always', str(here/'solve_probe.py'), str(root/'fields.npz')],
                       capture_output=True, text=True, env=env, cwd=root)
    entry = dict(diagnostic=dict(exit=d.returncode, ok_rows=sum(' OK ' in r for r in rows), slow_rows=[r for r in rows if ' SLOW ' in r],
                                 rows=rows, stderr=d.stderr[-1500:]),
                 solve_exit=s.returncode, solve_stderr=s.stderr[-3000:])
    if s.returncode == 0:
        entry['solve'] = json.loads(s.stdout)
        f = dict(np.load(root/'fields.npz'))
        if base is None: base = f
        entry['max_rel_l2_vs_baseline'] = max(float(np.linalg.norm(f[k]-base[k])/np.linalg.norm(base[k])) for k in base)
    report[name] = entry
    print(name, 'diag exit', d.returncode, 'OK', entry['diagnostic']['ok_rows'], 'SLOW', entry['diagnostic']['slow_rows'],
          '| solve', s.returncode, entry.get('solve', {}).get('loaders'), [r['wall_s'] for r in entry.get('solve', {}).get('runs', [])],
          entry.get('max_rel_l2_vs_baseline'), flush=True)
out.write_text(json.dumps(report, indent=1)+'\n')
