"""Run a complete tiny local sweep or an HPC dry submission plus local workers.

No sbatch command is invoked. HPC worker processes execute locally, including
their frozen runtime, spawned solve pools, manifests and restart artifacts.
"""
import importlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys


def main():
    root, kind, output = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(root / 'tools/GHOST'))
    is_bor = kind.endswith('bor')
    is_hpc = kind.startswith('hpc')
    module_name = ('hpc.' if is_hpc else 'runs.local_') + ('bor_driver' if is_bor else 'twod_driver')
    driver = importlib.import_module('ghost_backend.' + module_name)
    driver.load_default_settings()
    settings = driver.current_settings()
    geom = output / 'geometry'
    geom.mkdir()
    empty = output / 'empty'
    empty.mkdir()
    if is_bor:
        points = [(0.03 * math.sin(math.pi * i / 16), 0.03 * math.cos(math.pi * i / 16))
                  for i in range(17)]
    else:
        points = [(0.03 * math.cos(-2 * math.pi * i / 24), 0.03 * math.sin(-2 * math.pi * i / 24))
                  for i in range(25)]
    rows = '\n'.join(' '.join(str(v) for v in (*a, *b)) for a, b in zip(points[:-1], points[1:]))
    (geom / 'body.geo').write_text('Title: driver smoke\nSegment: body 2\nproperties: 2 1 0 0 0\n' + rows
                                  + '\nIBCS_Resistances:\n\nDielectrics:\n')
    changes = dict(OUTPUT_DIR=str(output / 'runs'), FREQUENCIES_GHZ=[0.3], AZIMUTHS_DEG=[0., 90.],
                   GEOMETRY_UNITS='meters', MESH_CERTIFICATION=False)
    if is_bor:
        changes.update(GEOMETRY_DIRS=[str(geom)], ELEVATIONS_DEG=[0.], N_MODES=8,
                       MAX_ELEMENTS=500, WORKERS_PER_UNIT=1, BLAS_THREADS_PER_WORKER=1,
                       TABLE_PRECISION='double', ASSEMBLY='streaming')
        if not is_hpc:
            changes['WORKERS'] = 1
    else:
        changes.update(FRD_DIR=str(geom), OPN_DIR=str(empty), FACTORIZATION='dense',
                       MESH_STRATEGY='global', BASIS_ORDER=1, MESH_GRADING=False)
        if not is_hpc:
            changes.update(WORKERS=1, PLANNING_WORKERS=1, MAX_SOLVE_GB=2.)
    if is_hpc:
        changes.update(SUBMIT=False, N_NODES=1, N_JOBS=1, CORES_PER_NODE=1,
                       MAX_WORKERS_PER_NODE=1, MEM_PER_NODE='4G', PYTHON_EXE=sys.executable)
    settings.update({k: v for k, v in changes.items() if k in settings})
    script = output / 'driver.py'
    script.write_text('\n'.join(k + ' = ' + repr(v) for k, v in settings.items())
                      + '\n\nif __name__ == "__main__":\n'
                      + '    from ghost_backend.' + module_name + ' import run\n'
                      + '    run(globals(), __file__)\n')
    env = dict(os.environ, PYTHONPATH=str(root / 'tools/GHOST'))
    with (output / 'run.log').open('w') as stream:
        subprocess.run([sys.executable, str(script)], env=env, stdout=stream,
                       stderr=subprocess.STDOUT, check=True, timeout=240)
    runs = list((output / 'runs').glob('run_*'))
    assert len(runs) == 1, runs
    run = runs[0]
    if is_hpc:
        copied = run / 'driver_configured.py'
        assert copied.is_file(), list(run.iterdir())
        env['PYTHONPATH'] = str(run / 'runtime')
        for attempt in ('worker', 'resume'):
            with (output / (attempt + '.log')).open('w') as stream:
                subprocess.run([sys.executable, str(copied), '--worker', str(run), '0', '0'],
                               env=env, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=240)
    artifacts = sorted(run.rglob('*.grim'))
    assert artifacts, list(run.iterdir())
    import numpy as np
    for path in artifacts:
        with np.load(path, allow_pickle=False) as data:
            assert data.files, path
    # A frozen runtime must contain the newly extracted mandatory modules.
    runtime = run / 'runtime' / 'ghost_backend'
    for name in ('runs/driver_settings.py', 'runs/worker_pipeline.py', 'bor/constraints.py',
                 'bor/storage.py', 'bor/validation.py'):
        assert (runtime / name).is_file(), (runtime, name)
    summary = dict(kind=kind, artifacts=[str(p.relative_to(run)) for p in artifacts],
                   frozen_modules_present=True, hpc_resume_executed=is_hpc)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
