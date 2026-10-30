"""A/B timing of Codex's inverse-construction checks on the ordinary 15 GHz inlet.

Arms:
  current  - the working tree as it is now (with the construction checks)
  baseline - a copy of the working tree with Codex's seven saved baseline files
             restored and compressed/construction.py removed (everything else equal)

Order is current, baseline, baseline, current. Automatic CPU profile, 12 GiB cap,
same harness and environment as Codex_audit/resource_efficiency_20261029/study.py.
"""
import hashlib, json, os, shutil, subprocess, sys, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]                      # ghost_backend
CODEX = ROOT/'Codex_audit'/'inverse_construction_20261029'
GIB = 1024**3


def save(path, value):
    path.write_text(json.dumps(value, indent=2, default=lambda x: x.tolist() if hasattr(x, 'tolist') else str(x))+'\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_baseline():
    target = HERE/'baseline_tree'/'ghost_backend'
    if target.exists():
        raise FileExistsError('Refusing to overwrite baseline tree')
    skip = shutil.ignore_patterns('Codex_audit', 'Claude_audit', 'tests', '__pycache__', '.git', 'scratch', 'trials', '*.npy', '*.npz')
    shutil.copytree(ROOT, target, ignore=skip)
    restored = {}
    for saved in sorted((CODEX/'baseline').glob('*.py')):
        relative = saved.name.replace('__', '/', 1)
        shutil.copyfile(saved, target/relative)
        restored[relative] = sha(saved)
    (target/'compressed'/'construction.py').unlink()
    return target.parent, restored


def geometry():
    import importlib.util
    spec = importlib.util.spec_from_file_location('geometry_source', ROOT/'Codex_audit'/'resource_efficiency_20261029'/'study.py')
    source = importlib.util.module_from_spec(spec); spec.loader.exec_module(source)
    return source.geometry('inlet')


def collect_construction(metadata, found):
    # The execution systems are the canonical build list. Channel summaries
    # and shadow observations repeat these same records.
    return [item['construction']
            for system in metadata.get('experimental_cpu', {}).get('systems', [])
            for item in system.get('preconditioners', []) if 'construction' in item]


def remove_temporary(name):
    if name not in ('baseline_tree', 'scratch'):
        raise ValueError('Not a temporary trial directory')
    directory = (HERE/name).resolve()
    if directory.parent != HERE.resolve():
        raise ValueError('Temporary directory escaped trial root')
    if directory.exists():
        shutil.rmtree(directory)


def worker(directory):
    import numpy as np
    from ghost_backend.twod import solver as solver_module
    from ghost_backend.twod.solver import solve_monostatic_rcs_2d_certified
    from ghost_backend.execution import memory_budget as mb
    from ghost_backend.execution.options import automatic_options, execution_scope, effective_assembly_threads, blas_thread_reservation
    case = json.loads((directory/'case.json').read_text())
    options = automatic_options(ram_budget_gib=12.)
    options['temporary_directory'] = str(HERE/'scratch')
    request = dict(geometry_snapshot=json.loads((HERE/'inlet_geometry.json').read_text()), frequencies_ghz=[15.],
        elevations_deg=list(range(361)), geometry_units='inches', max_panels=100000)
    package_root = Path(solver_module.__file__).resolve().parents[1]
    record = dict(case=case, ghost_backend_path=str(package_root),
        source_hashes={name: sha(package_root/name) for name in ['execution/memory_budget.py',
            'compressed/preconditioner_hints.py', 'compressed/construction.py',
            'compressed/worker_pool.py', 'twod/assembly/polynomial_pair.py',
            'geometry/material_columns.py', 'compressed/factor.py', 'compressed/hmatrix.py',
            'compressed/hmatrix_factor.py', 'compressed/inverse.py', 'linalg/hierarchical.py']
            if (package_root/name).exists()})
    started = time.perf_counter()
    with execution_scope(options), mb.scope() as ledger:
        record['initial_execution'] = dict(assembly_threads=effective_assembly_threads(), blas_reservation=blas_thread_reservation())
        try:
            result = solve_monostatic_rcs_2d_certified(**request, execution_options=options)
            record['solve_seconds'] = time.perf_counter()-started
            metadata = result['metadata']; save(directory/'metadata.json', metadata)
            fields = {p: np.asarray([complex(v['rcs_amp_real'], v['rcs_amp_imag']) for v in values])
                      for p, values in result['co_solved_samples'].items()}
            np.savez(directory/'fields.npz', **fields)
            record.update(status='passed', certified=bool(metadata['quality_gate']['passed'] and metadata['mesh_convergence_certified']),
                linear_node_count=metadata.get('linear_node_count'),
                stage_seconds=metadata.get('runtime_profile', {}).get('stage_seconds', {}),
                construction=collect_construction(metadata, []))
        except Exception as exc:
            record.update(status='failed', error_type=type(exc).__name__, error=str(exc))
            traceback.print_exc()
        finally:
            record['elapsed_seconds'] = time.perf_counter()-started
            save(directory/'result.json', record)


def run(name, arm, pythonpath):
    import psutil
    directory = HERE/'runs'/name; directory.mkdir(parents=True, exist_ok=False)
    save(directory/'case.json', dict(name=name, arm=arm))
    (HERE/'scratch').mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONPATH=pythonpath, OPENBLAS_NUM_THREADS='4', MKL_NUM_THREADS='4', OMP_NUM_THREADS='4',
               TEMP=str(HERE/'scratch'), TMP=str(HERE/'scratch'), PYTHONIOENCODING='utf-8')
    started = time.monotonic(); peak_rss = peak_private = 0; reason = None
    with (directory/'worker.log').open('w') as log:
        # Run from the scratch folder so the working directory can't shadow either tree.
        child = subprocess.Popen([sys.executable, '-u', str(Path(__file__).resolve()), '--worker', str(directory)],
                                 cwd=HERE/'scratch', env=env, stdout=log, stderr=subprocess.STDOUT)
        parent = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                family = [parent]+parent.children(recursive=True); infos = [p.memory_info() for p in family]
                peak_rss = max(peak_rss, sum(x.rss for x in infos))
                peak_private = max(peak_private, sum(getattr(x, 'private', 0) for x in infos))
                if max(peak_rss, peak_private) > 14*GIB: reason = '14 GiB guard'
                if psutil.virtual_memory().available < 2*GIB: reason = '2 GiB host reserve'
                if time.monotonic()-started > 900: reason = 'time guard'
                if reason:
                    for process in reversed(family):
                        try: process.kill()
                        except psutil.NoSuchProcess: pass
                    child.wait(); break
            except psutil.NoSuchProcess:
                pass
            time.sleep(.25)
    monitor = dict(returncode=child.returncode, stop_reason=reason, peak_tree_rss=peak_rss,
                   peak_tree_private=peak_private, wall_seconds=time.monotonic()-started)
    save(directory/'monitor.json', monitor)
    result = json.loads((directory/'result.json').read_text()) if (directory/'result.json').exists() else dict(status='stopped')
    print(name, arm, result.get('status'), result.get('solve_seconds'), reason, flush=True)
    return result


def summarize():
    import numpy as np
    rows = []
    for directory in sorted((HERE/'runs').iterdir()):
        result = json.loads((directory/'result.json').read_text())
        monitor = json.loads((directory/'monitor.json').read_text())
        stages = result.get('stage_seconds', {})
        checks = sum(item.get('checks', 0) for item in result.get('construction', []))
        rows.append(dict(name=directory.name, arm=result['case']['arm'], status=result.get('status'),
            certified=result.get('certified'), solve_seconds=result.get('solve_seconds'),
            factorization_seconds=stages.get('factorization'), linear_solve_seconds=stages.get('linear_solve'),
            hmatrix_assembly_seconds=stages.get('hmatrix_assembly'), construction_checks=checks,
            construction_records=len(result.get('construction', [])),
            construction_live_checks=sum(x.get('live_checks', 0) for x in result.get('construction', [])),
            construction_reused_checks=sum(x.get('reused_observations', 0) for x in result.get('construction', [])), linear_node_count=result.get('linear_node_count'),
            peak_tree_rss_gib=monitor['peak_tree_rss']/GIB, peak_tree_private_gib=monitor['peak_tree_private']/GIB,
            ghost_backend_path=result.get('ghost_backend_path')))
    fields = {}
    for row in rows:
        path = HERE/'runs'/row['name']/'fields.npz'
        if path.exists():
            with np.load(path) as data: fields[row['name']] = {k: data[k] for k in data.files}
    reference = next(iter(fields.values()), None); differences = {}
    if reference is not None:
        for name, values in fields.items():
            differences[name] = {p: float(np.max(abs(values[p]-reference[p]))/max(1., float(np.max(abs(reference[p]))))) for p in reference}
    summary = dict(rows=rows, max_relative_field_difference_vs_first_run=differences)
    for arm in ('current', 'baseline'):
        times = [r['solve_seconds'] for r in rows if r['arm'] == arm and r['solve_seconds']]
        factor = [r['factorization_seconds'] for r in rows if r['arm'] == arm and r['factorization_seconds']]
        summary[arm+'_mean_solve_seconds'] = sum(times)/len(times) if times else None
        summary[arm+'_mean_factorization_seconds'] = sum(factor)/len(factor) if factor else None
    save(HERE/'summary.json', summary)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(Path(sys.argv[2])); sys.exit(0)
    if (HERE/'runs').exists():
        sys.exit('runs/ already exists; move it aside first.')
    save(HERE/'inlet_geometry.json', geometry())
    baseline_parent, restored = build_baseline()
    save(HERE/'baseline_restored_files.json', restored)
    current_path = str(ROOT.parent)
    baseline_path = str(baseline_parent)+os.pathsep+str(ROOT.parent)
    plan = [('1_current', 'current', current_path), ('2_baseline', 'baseline', baseline_path),
            ('3_baseline', 'baseline', baseline_path), ('4_current', 'current', current_path)]
    for name, arm, path in plan:
        run(name, arm, path)
    summarize()
    remove_temporary('baseline_tree')
    remove_temporary('scratch')
