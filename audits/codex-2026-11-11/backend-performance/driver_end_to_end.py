"""End-to-end driver run for one checkout: python drv.py <root> <kind> <outdir> <certify 0/1>
kind in local-twod, local-bor, hpc-twod, hpc-bor.  Writes <outdir>/arrays.npz (numerical arrays
of every artifact, keyed by relative path) and <outdir>/events.json (restart behaviour)."""
import importlib, json, math, os, subprocess, sys, shutil, time
from pathlib import Path
import numpy as np
root, kind, output, certify = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).resolve(), sys.argv[4] == '1'
output.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(root / 'tools/GHOST'))
is_bor, is_hpc = kind.endswith('bor'), kind.startswith('hpc')
module_name = ('hpc.' if is_hpc else 'runs.local_') + ('bor_driver' if is_bor else 'twod_driver')
driver = importlib.import_module('ghost_backend.' + module_name)
driver.load_default_settings()
settings = driver.current_settings()
geom = output / 'geometry'; geom.mkdir(); other = output / 'other'; other.mkdir()
def write(path, pts, props):
    rows = '\n'.join(' '.join(repr(float(v)) for v in (*a, *b)) for a, b in zip(pts[:-1], pts[1:]))
    path.write_text('Title: t\nSegment: body 2\nproperties: ' + props + '\n' + rows + '\nIBCS_Resistances:\n10 constant 80 -40 0 0\nDielectrics:\n')
if is_bor:
    write(geom / 'sphere.geo', [(0.03*math.sin(math.pi*i/16), 0.03*math.cos(math.pi*i/16)) for i in range(17)], '2 1 0 0 0')
    write(geom / 'ibc.geo', [(0.02*math.sin(math.pi*i/12), 0.035*math.cos(math.pi*i/12)) for i in range(13)], '2 1 10 0 0')
else:
    write(geom / 'circle.geo', [(0.03*math.cos(-2*math.pi*i/24), 0.03*math.sin(-2*math.pi*i/24)) for i in range(25)], '2 1 0 0 0')
    write(other / 'ellipse.geo', [(0.04*math.cos(-2*math.pi*i/32), 0.02*math.sin(-2*math.pi*i/32)) for i in range(33)], '2 1 10 0 0')
changes = dict(OUTPUT_DIR=str(output / 'runs'), FREQUENCIES_GHZ=[0.3, 0.9], AZIMUTHS_DEG=[0., 40., 90.],
               GEOMETRY_UNITS='meters', MESH_CERTIFICATION=certify)
if is_bor:
    changes.update(GEOMETRY_DIRS=[str(geom)], ELEVATIONS_DEG=[0.], N_MODES=8, MAX_ELEMENTS=500, WORKERS_PER_UNIT=1,
                   BLAS_THREADS_PER_WORKER=1, TABLE_PRECISION='double', ASSEMBLY='streaming')
    if not is_hpc: changes['WORKERS'] = 1
else:
    changes.update(FRD_DIR=str(geom), OPN_DIR=str(other), FACTORIZATION='automatic', MESH_STRATEGY='global', BASIS_ORDER=1, MESH_GRADING=True)
    if not is_hpc: changes.update(WORKERS=1, PLANNING_WORKERS=1, MAX_SOLVE_GB=2.)
if is_hpc:
    changes.update(SUBMIT=False, N_NODES=1, N_JOBS=1, CORES_PER_NODE=1, MAX_WORKERS_PER_NODE=1, MEM_PER_NODE='4G', PYTHON_EXE=sys.executable)
unknown = sorted(k for k in changes if k not in settings)
settings.update({k: v for k, v in changes.items() if k in settings})
script = output / 'driver.py'
script.write_text('\n'.join(k + ' = ' + repr(v) for k, v in settings.items()) + '\n\nif __name__ == "__main__":\n    from ghost_backend.' + module_name + ' import run\n    run(globals(), __file__)\n')
env = dict(os.environ, PYTHONPATH=str(root / 'tools/GHOST'), OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
events = dict(kind=kind, certify=certify, settings_not_in_driver=unknown)
def call(cmd, log, env=env):
    with (output / log).open('w') as stream:
        return subprocess.run(cmd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=400).returncode
events['submit_rc'] = call([sys.executable, str(script)], 'run.log')
runs = sorted((output / 'runs').glob('run_*')); assert len(runs) == 1, runs
run = runs[0]
def grims(): return sorted(run.rglob('*.grim'))
def stamp(): return {str(p.relative_to(run)): p.stat().st_mtime_ns for p in grims()}
if is_hpc:
    wenv = dict(env, PYTHONPATH=str(run / 'runtime'))
    worker = [sys.executable, str(run / 'driver_configured.py'), '--worker', str(run), '0', '0']
    events['worker_rc'] = call(worker, 'worker.log', wenv)
    first = stamp()
    events['resume_rc'] = call(worker, 'resume.log', wenv)
    events['resume_rewrote'] = sorted(k for k, v in stamp().items() if first.get(k) != v)
    # partial restart: remove one artifact, rerun, only that one may be rewritten
    victim = ([p for p in grims() if 'by_frequency' in str(p)] or grims())[0]; keep = {k: v for k, v in stamp().items() if k != str(victim.relative_to(run))}
    with np.load(victim, allow_pickle=False) as d: before = {k: d[k].copy() for k in d.files if d[k].dtype.kind in 'fc'}
    victim.unlink()
    removed_claims = [c.unlink() or c.name for c in (run / 'claims').glob('*') if victim.name in c.name or victim.stem.split('_', 1)[-1] in c.name and '+' in c.name]
    events['partial_claims_removed'] = len(removed_claims)
    events['partial_rc'] = call(worker, 'partial.log', wenv)
    after = stamp()
    events['partial_restored_victim'] = victim.exists()
    events['partial_rewrote_others'] = sorted(k for k, v in keep.items() if after.get(k) != v)
    if victim.exists():
        with np.load(victim, allow_pickle=False) as d: events['partial_arrays_equal'] = all(np.array_equal(before[k], d[k], equal_nan=True) for k in before)
arrays = {}
for path in grims():
    with np.load(path, allow_pickle=False) as data:
        for key in data.files:
            if data[key].dtype.kind in 'fciub':
                arrays[str(path.relative_to(run)).replace('\\', '/') + '::' + key] = data[key]
events['artifacts'] = sorted({k.split('::')[0] for k in arrays})
np.savez(output / 'arrays.npz', **arrays)
runtime = run / 'runtime' / 'ghost_backend'
events['frozen_runtime_files'] = sum(1 for _ in runtime.rglob('*.py')) if runtime.is_dir() else None
if is_hpc:
    # tampered input: the worker must refuse to reuse or write
    gone = ([p for p in grims() if 'by_frequency' in str(p)] or grims())[0]
    stem = gone.stem.split('GHz_', 1)[-1]
    target = next(p for p in sorted((run / 'inputs').rglob('*.geo')) if p.stem == stem)
    target.write_text(target.read_text() + '\n# edited after submission\n')
    gone.unlink()
    [c.unlink() for c in (run / 'claims').glob('*') if gone.name in c.name or gone.stem.split('_', 1)[-1] in c.name and '+' in c.name]
    events['tamper_rc'] = call(worker, 'tamper.log', wenv)
    text = (output / 'tamper.log').read_text()
    events['tamper_restored_victim'] = gone.exists()
    events['tamper_message'] = next((l.strip()[:160] for l in text.splitlines() if 'changed' in l.lower()), text.strip().splitlines()[-1][:160] if text.strip() else '')
    events['tamper_artifact_count'] = len(grims())
(output / 'events.json').write_text(json.dumps(events, indent=1, sort_keys=True))
print(json.dumps({k: v for k, v in events.items() if k != 'artifacts'}, sort_keys=True))
