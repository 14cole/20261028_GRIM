"""Reproducible, isolated 12-foot airfoil certification and backend comparison.

Run from any directory with Python. Each case uses four threads and an 8 GiB
admission budget. Two repetitions run in alternating backend order. A case is
limited to 20 minutes; a failed backend is not repeated. Outputs stay beside
this script. Time includes the certified solve, not imports or file export.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'benchmark_12ft'
sys.path.insert(0, str(ROOT.parent))


def save(path, value):
    path.write_text(json.dumps(value, indent=2, default=lambda x: x.tolist() if hasattr(x, 'tolist') else str(x)),
                    encoding='utf-8')


def worker(mode, repeat):
    import numpy as np
    from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot, snapshot_to_geometry_text
    from ghost_backend.execution.selection import select_backend
    from ghost_backend.execution.options import validate_options
    from ghost_backend.twod.solver import solve_monostatic_rcs_2d_certified
    directory = OUT / f'{mode}_{repeat}'
    directory.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'trials/airfoil_matrix_20261027_full/input_airfoil.geo'
    snapshot = build_geometry_snapshot(*parse_geometry(source.read_text()))
    xs = [p[k] for seg in snapshot['segments'] for p in seg['point_pairs'] for k in ('x1', 'x2')]
    scale = 144. / (max(xs) - min(xs))
    for seg in snapshot['segments']:
        for p in seg['point_pairs']:
            for k in ('x1', 'y1', 'x2', 'y2'):
                p[k] *= scale
    (directory / 'airfoil_12ft.geo').write_text(snapshot_to_geometry_text(snapshot), encoding='utf-8')
    options = validate_options(dict(factorization=mode, mesh_strategy='adaptive', basis_order=1,
        mesh_grading=True, assembly_threads=4, blas_threads=4, ram_budget_gib=8., compressed_storage_mib=0))
    args = dict(geometry_snapshot=snapshot, frequencies_ghz=[1.], elevations_deg=list(range(361)),
                geometry_units='inches', max_panels=100000)
    record = dict(mode=mode, repetition=repeat, frequency_ghz=1., chord_inches=144., scale=scale,
                  angles=361, execution_options=options, source_geometry_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    record['forecast'] = select_backend(args, options, certified=True)
    save(directory / 'request.json', record)
    last = [0.]
    def progress(done, total, message=''):
        now = time.monotonic()
        if now - last[0] > 10:
            print(f'{mode} {repeat}: {done}/{total} {message}', flush=True)
            last[0] = now
    started = time.perf_counter()
    try:
        result = solve_monostatic_rcs_2d_certified(**args, solver_method='experimental_cpu',
            execution_options=options, progress_callback=progress)
        record['solve_wall_seconds'] = time.perf_counter() - started
        metadata = result['metadata']
        save(directory / 'metadata.json', metadata)
        fields = {pol: np.asarray([complex(row['rcs_amp_real'], row['rcs_amp_imag'])
                                   for row in values]) for pol, values in result['co_solved_samples'].items()}
        np.savez(directory / 'fields.npz', **fields)
        record.update(status='ok', mesh_convergence_certified=metadata.get('mesh_convergence_certified'),
                      quality_gate=metadata.get('quality_gate'), panels=metadata.get('panel_count'),
                      basis_order=metadata.get('polynomial_degree'), actual_options=metadata.get('execution_options'),
                      metrics=metadata.get('runtime_profile', {}))
    except Exception as exc:
        record.update(status='failed', solve_wall_seconds=time.perf_counter() - started,
                      error_type=type(exc).__name__, error=str(exc))
        traceback.print_exc()
    save(directory / 'result.json', record)
    print(json.dumps({k: record.get(k) for k in ('mode','repetition','status','solve_wall_seconds','error')}), flush=True)


def controller():
    import numpy as np
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, OPENBLAS_NUM_THREADS='4', MKL_NUM_THREADS='4', OMP_NUM_THREADS='4',
               GHOST_DENSE_BACKEND='cpu', GHOST_LU_PRECISION='double',
               GHOST_TIMING_CACHE_DIR=str(OUT / 'timing_cache'))
    records, failed = [], set()
    for repeat in (1, 2):
        for mode in ('dense', 'compressed'):
            if mode in failed:
                continue
            directory = OUT / f'{mode}_{repeat}'
            directory.mkdir(exist_ok=True)
            if (directory / 'result.json').exists():
                raise RuntimeError('Refusing to overwrite existing benchmark: ' + str(directory))
            print(f'Starting {mode} repetition {repeat}', flush=True)
            with (directory / 'worker.log').open('w', encoding='utf-8') as log:
                proc = subprocess.Popen([sys.executable, '-u', str(Path(__file__).resolve()), '--worker', mode,
                                         '--repeat', str(repeat)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
                try:
                    proc.wait(timeout=1200)
                except subprocess.TimeoutExpired:
                    import psutil
                    parent = psutil.Process(proc.pid)
                    for child in parent.children(recursive=True):
                        try:
                            child.kill()
                        except psutil.NoSuchProcess:
                            pass
                    proc.kill(); proc.wait()
            path = directory / 'result.json'
            row = json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(
                mode=mode, repetition=repeat, status='failed', error='Worker exited or timed out before result', returncode=proc.returncode)
            if row['status'] != 'ok':
                failed.add(mode)
            records.append(row)
            save(OUT / 'summary.json', dict(cases=records))
            print(json.dumps({k: row.get(k) for k in ('mode','repetition','status','solve_wall_seconds','error')}), flush=True)
    comparisons = []
    for repeat in (1, 2):
        a, b = OUT / f'dense_{repeat}/fields.npz', OUT / f'compressed_{repeat}/fields.npz'
        if a.exists() and b.exists():
            with np.load(a) as dense, np.load(b) as compressed:
                for pol in dense.files:
                    x, y = dense[pol], compressed[pol]
                    if x.shape != y.shape:
                        comparisons.append(dict(repetition=repeat, polarization=pol, error='Shape mismatch'))
                        continue
                    comparisons.append(dict(repetition=repeat, polarization=pol,
                        max_complex_difference_over_dense_peak=float(np.max(abs(x-y))/max(float(np.max(abs(x))),1e-300)),
                        all_finite=bool(np.all(np.isfinite(x)) and np.all(np.isfinite(y)))))
    save(OUT / 'summary.json', dict(cases=records, field_comparisons=comparisons,
        note='Measured current-code certified solves; field agreement is not an independent physical reference.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=['dense','compressed'])
    parser.add_argument('--repeat', type=int, default=1)
    args = parser.parse_args()
    worker(args.worker, args.repeat) if args.worker else controller()
