"""Resource forecasts and bounded, isolated synthetic inlet benchmarks.

Synthetic PEC contours are examples, not the user's engineering geometry.
No production solver code or acceptance thresholds are changed.
"""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT.parent))


def save(path, data):
    path.write_text(json.dumps(data, indent=2, default=lambda x: x.tolist() if hasattr(x, 'tolist') else str(x)), encoding='utf-8')


def geometry(name):
    if name == 'airfoil':
        from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
        source = ROOT/'trials/airfoil_matrix_20261027_full/input_airfoil.geo'
        snapshot = build_geometry_snapshot(*parse_geometry(source.read_text()))
        xs = [p[k] for s in snapshot['segments'] for p in s['point_pairs'] for k in ('x1','x2')]
        scale = 144/(max(xs)-min(xs))
        for s in snapshot['segments']:
            for p in s['point_pairs']:
                for k in ('x1','x2','y1','y2'):
                    p[k] *= scale
        return snapshot
    material = name if name in ('inlet_dielectric', 'inlet_high_contrast') else None
    if material:
        name = 'inlet'
    if name == 'rectangle':
        points = [(0, 0), (144, 0), (144, 36), (0, 36)]
    else:
        depth, mouth = (48, 12) if name == 'inlet' else (72, 3)
        lower, upper = (36-mouth)/2, (36+mouth)/2
        points = [(0, 0), (144, 0), (144, lower), (144-depth, lower),
                  (144-depth, upper), (144, upper), (144, 36), (0, 36)]
    # Clockwise contour, standard air-facing TYPE 2 convention.
    points = list(reversed(points))
    points.append(points[0])
    pairs = [dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1]) for a, b in zip(points[:-1], points[1:])]
    snapshot = dict(segments=[dict(name=name, seg_type=2, properties=['2', '-20', '0', '0', '0'], point_pairs=pairs)], ibcs=[], dielectrics=[])
    if material:
        snapshot['segments'][0].update(seg_type=3, properties=['3','-20','0','1','0'])
        snapshot['dielectrics'] = [['1','4','-.04','1','0']] if material == 'inlet_dielectric' else [['1','101.19','-11.88','3.45','-3.47']]
    return snapshot


def forecast():
    from ghost_backend.execution.options import validate_options, execution_scope
    from ghost_backend.execution.selection import _forecast_backend
    from ghost_backend.twod import solver
    from ghost_backend.geometry.io import snapshot_to_geometry_text
    rows = []
    for name in ('rectangle', 'inlet', 'narrow_inlet', 'inlet_dielectric', 'inlet_high_contrast'):
        snapshot = geometry(name)
        (HERE / (name + '.geo')).write_text(snapshot_to_geometry_text(snapshot), encoding='utf-8')
        perimeter = sum(math.hypot(p['x2']-p['x1'], p['y2']-p['y1']) for p in snapshot['segments'][0]['point_pairs'])/12
        for freq in (.1, .3, 1., 3., 10.):
            options = validate_options(dict(factorization='adaptive', mesh_strategy='adaptive', basis_order=1,
                mesh_grading=True, assembly_threads=4, blas_threads=4, ram_budget_gib=8., compressed_storage_mib=0))
            args = dict(geometry_snapshot=snapshot, frequencies_ghz=[freq], elevations_deg=list(range(361)),
                        geometry_units='inches', max_panels=100000)
            resources = []
            row = dict(geometry=name, frequency_ghz=freq, perimeter_feet=perimeter, length_wavelengths=3.6576*freq*1e9/solver.C0,
                       kind='initial certification candidate forecasts, not completed solves', settings=options)
            started = time.perf_counter()
            try:
                result = _forecast_backend(args, options, certified=True, resource_records=resources)
                row['selection'] = {k: v for k, v in result.items() if k != 'meshes'}
            except Exception as exc:
                row['admission_error'] = str(exc)
            row['candidate_resources'] = []
            for resource, mesh_options in resources:
                evidence = dict(resource=resource, basis_order=mesh_options['basis_order'], forecasts={})
                for mode in ('dense', 'compressed'):
                    measured = dict(resource)
                    with execution_scope(dict(mesh_options, factorization=mode)):
                        peak = solver._estimate_memory_gb(resource['nodes'], False, n_regions=resource['n_regions'],
                            system_dofs=resource['system_dofs'], operator_matrices=resource['operator_matrices'],
                            dense_resources=measured, n_rhs=361, solver_method='experimental_cpu')
                    evidence['forecasts'][mode] = dict(peak_gib=peak, details=measured.get('memory_estimate'))
                row['candidate_resources'].append(evidence)
            row['peak_gib'] = {m: max((r['forecasts'][m]['peak_gib'] for r in row['candidate_resources']), default=None) for m in ('dense', 'compressed')}
            row['max_unknowns'] = max((r['resource']['system_dofs'] for r in row['candidate_resources']), default=0)
            row['seconds'] = time.perf_counter()-started
            rows.append(row)
            save(HERE/'forecasts.json', rows)
            print(json.dumps({k: row[k] for k in ('geometry','frequency_ghz','max_unknowns','peak_gib','seconds')}), flush=True)


def worker(args):
    import numpy as np
    from ghost_backend.execution.options import validate_options
    from ghost_backend.execution.selection import select_backend
    from ghost_backend.twod.solver import solve_monostatic_rcs_2d_certified
    if args.disable_hint:
        from ghost_backend.compressed import preconditioner_hints
        preconditioner_hints.try_build = lambda factor: False
    if args.leaf:
        from ghost_backend.compressed import hmatrix
        hmatrix.LEAF = args.leaf
    if args.preconditioner is not None:
        # Experimental inverse-build accuracy only. Operator, residual and
        # mesh-convergence acceptance gates retain all production settings.
        import ghost_backend.compressed.factor as factor_module
        factor_module.PRECONDITIONER_TOLERANCE = args.preconditioner
    if args.disable_upgrade:
        from ghost_backend.compressed.factor import CompressedFactor
        CompressedFactor._upgrade_preconditioner = lambda self: False
    directory = HERE/'benchmarks'/args.name
    directory.mkdir(parents=True, exist_ok=True)
    if (directory/'result.json').exists():
        raise RuntimeError('Refusing to overwrite '+str(directory))
    options = validate_options(dict(factorization=args.mode, mesh_strategy='adaptive', basis_order=1,
        mesh_grading=True, assembly_threads=args.threads, blas_threads=args.threads, ram_budget_gib=args.ram,
        compressed_storage_mib=0, angle_batch_size=args.batch, rhs_compression=args.rhs))
    request = dict(geometry_snapshot=geometry(args.geometry), frequencies_ghz=[args.frequency],
                   elevations_deg=list(range(361)), geometry_units='inches', max_panels=20000)
    record = dict(name=args.name, geometry=args.geometry, frequency_ghz=args.frequency, options=options,
                  synthetic=args.geometry != 'airfoil', angle_count=361,
                  experimental_preconditioner_tolerance=args.preconditioner,
                  experimental_disable_upgrade=args.disable_upgrade)
    record.update(experimental_disable_hint=args.disable_hint, experimental_leaf=args.leaf)
    save(directory/'request.json', dict(record, request=request))
    started = time.perf_counter()
    last = [0.]
    def progress(done, total, message=''):
        if time.monotonic()-last[0] > 10:
            print(str(message), flush=True)
            last[0] = time.monotonic()
    try:
        record['preflight'] = select_backend(request, options, certified=True)
        record['preflight_seconds'] = time.perf_counter()-started
        started = time.perf_counter()
        result = solve_monostatic_rcs_2d_certified(**request, solver_method='experimental_cpu',
            execution_options=options, progress_callback=progress)
        record['solve_seconds'] = time.perf_counter()-started
        metadata = result['metadata']
        save(directory/'metadata.json', metadata)
        fields = {p: np.asarray([complex(r['rcs_amp_real'], r['rcs_amp_imag']) for r in values])
                  for p, values in result['co_solved_samples'].items()}
        np.savez(directory/'fields.npz', **fields)
        record.update(status='ok', panels=metadata.get('panel_count'), basis_order=metadata.get('polynomial_degree'),
            quality_gate=metadata.get('quality_gate'), mesh_convergence_certified=metadata.get('mesh_convergence_certified'),
            runtime_profile=metadata.get('runtime_profile'))
    except Exception as exc:
        record.update(status='failed', elapsed_seconds=time.perf_counter()-started, error_type=type(exc).__name__, error=str(exc))
        traceback.print_exc()
    save(directory/'result.json', record)
    print(json.dumps({k: record.get(k) for k in ('name','status','solve_seconds','panels','error')}), flush=True)


def run(args):
    directory = HERE/'benchmarks'/args.name
    directory.mkdir(parents=True, exist_ok=True)
    if (directory/'worker.log').exists():
        raise RuntimeError('Refusing to overwrite existing run '+str(directory))
    env = dict(os.environ, OPENBLAS_NUM_THREADS=str(args.threads), MKL_NUM_THREADS=str(args.threads),
        OMP_NUM_THREADS=str(args.threads), GHOST_DENSE_BACKEND='cpu', GHOST_LU_PRECISION='double',
        GHOST_TIMING_CACHE_DIR=str(HERE/'timing_cache'))
    command = [sys.executable, '-u', str(Path(__file__).resolve()), '--worker', '--name', args.name,
        '--geometry', args.geometry, '--mode', args.mode, '--frequency', str(args.frequency),
        '--threads', str(args.threads), '--batch', str(args.batch), '--rhs', args.rhs, '--ram', str(args.ram)]
    if args.disable_upgrade:
        command.append('--disable-upgrade')
    if args.disable_hint:
        command.append('--disable-hint')
    if args.leaf:
        command.extend(['--leaf', str(args.leaf)])
    if args.preconditioner is not None:
        command.extend(['--preconditioner', str(args.preconditioner)])
    import psutil
    with (directory/'worker.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        parent = psutil.Process(process.pid)
        start = time.monotonic()
        peak_rss = peak_private = 0
        stopped = None
        while process.poll() is None:
            try:
                family = [parent]+parent.children(recursive=True)
                memory = [p.memory_info() for p in family]
                rss = sum(m.rss for m in memory)
                private = sum(getattr(m, 'private', 0) for m in memory)
                peak_rss, peak_private = max(peak_rss,rss), max(peak_private,private)
                if max(rss, private) > 10*1024**3:
                    stopped = 'External audit guard: process-tree RSS or private commit exceeded 10 GiB'
                if time.monotonic()-start > 600:
                    stopped = 'External audit guard: 10 minute case timeout'
                if stopped:
                    for p in reversed(family):
                        try: p.kill()
                        except psutil.NoSuchProcess: pass
                    process.wait()
                    break
            except psutil.NoSuchProcess:
                pass
            time.sleep(.1)
    monitor = dict(returncode=process.returncode, process_tree_peak_rss_bytes=peak_rss,
        process_tree_peak_private_bytes=peak_private, elapsed_seconds=time.monotonic()-start,
        stopped=stopped, sample_interval_seconds=.1, scope='isolated parent plus descendants; shared RSS pages may be counted twice')
    save(directory/'monitor.json', monitor)
    if stopped:
        save(directory/'result.json', dict(status='stopped', name=args.name, error=stopped))
    print(json.dumps(monitor), flush=True)
    if (directory/'result.json').exists():
        result=json.loads((directory/'result.json').read_text())
        print(json.dumps({k: result.get(k) for k in ('name','status','solve_seconds','panels','error')}), flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--forecast', action='store_true')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--name', default='inlet_compressed_baseline')
    parser.add_argument('--geometry', choices=['rectangle','inlet','narrow_inlet','inlet_dielectric','inlet_high_contrast','airfoil'], default='inlet')
    parser.add_argument('--mode', choices=['dense','compressed','adaptive'], default='compressed')
    parser.add_argument('--frequency', type=float, default=1.)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--batch', type=int, default=256)
    parser.add_argument('--rhs', choices=['auto','on','off'], default='auto')
    parser.add_argument('--preconditioner', type=float, default=None)
    parser.add_argument('--ram', type=float, default=8.)
    parser.add_argument('--disable-upgrade', action='store_true')
    parser.add_argument('--disable-hint', action='store_true')
    parser.add_argument('--leaf', type=int, default=0)
    args=parser.parse_args()
    forecast() if args.forecast else worker(args) if args.worker else run(args)
