"""Local monostatic RCS sweep -- run_hpc_monostatic.py without SLURM.

One .grim per (geometry, frequency) unit is written to
<OUTPUT_DIR>/run_YYYYMMDD_HHMMSS/results/{FRD,OPN}/ as soon as that unit
finishes, named "<FREQ:.3f>GHz_<geometry_stem>.grim". Every file contains the
canonical VV and HH channels. The role folders can be passed directly to the
downstream subtraction tool.
each file carries its own source/runtime/input attestation inside the artifact,
so a resumed run verifies what it reuses without a sidecar per output.

Scheduling matches the HPC path. Units are costed from the mesh the solver will
actually build and run dearest-first, and concurrent solves are admitted
against a memory budget rather than filling every core regardless of unit size
-- one 40 GB geometry does not get eight copies of itself started on a 32 GB
laptop.

Edit the CONFIG block and run:

    python run_local_monostatic.py
"""
from ghost_backend.runs.driver_settings import DriverSettings
from ghost_backend.runs.inputs import unit_attestation_fields, verify_local_run_provenance
from ghost_backend.runs.worker_pipeline import WorkerAdapter, run_twod_unit, record_memory_evidence
from ghost_backend.execution.paths import backend_root as _backend_root
from ghost_backend.execution.options import (
    blas_thread_reservation,
    AUTOMATIC_LU_PRECISION, AUTOMATIC_SOLVER_METHOD, current_options,
)
from ghost_backend.runs.execution import driver_execution, unit_execution
from ghost_backend.runs.controls import DRIVER_CONTROL_DEFAULTS, run_control_summary

import json
import math
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import ghost_backend.hpc.scheduler as hpc_scheduler
from ghost_backend.runs.quality import accuracy_target_policy
from ghost_backend.execution.provenance import (
    backend_source_fingerprint,
    backend_source_inventory,
    describe_source_mismatch,
    embed_output_attestation,
    manifest_solve_spec_fingerprint,
    runtime_environment_fingerprint,
    runtime_environment_payload,
    verify_runtime_environment,
    stable_json_fingerprint,
    unit_solve_spec_fingerprint,
    verify_embedded_attestation,
)

from ghost_backend.runs.inputs import verify_local_unit_input as _verify_unit_input
from ghost_backend.runs.inputs import load_geometry_snapshot




# User parameters supplied by run_local_monostatic.py through run()/configure().
_PARAMETER_KEYS = (
    'FRD_DIR',
    'OPN_DIR',
    'FREQUENCIES_GHZ',
    'AZIMUTHS_DEG',
    'OUTPUT_DIR',
    'GEOMETRY_UNITS',
    'MESH_CERTIFICATION',
    'ACCURACY_TARGET',
    'WORKERS',
    'PLANNING_WORKERS',
    'MAX_SOLVE_GB',
    *DRIVER_CONTROL_DEFAULTS,
)
_SETTINGS = DriverSettings()
_SCRIPT = None


def current_settings():
    """Return an independent parameter dictionary for manifests and spawned workers."""
    return _SETTINGS.snapshot()


def configure(settings, *, script):
    """Capture a parameter block, keeping defaults for older advanced controls."""
    global _SETTINGS, _SCRIPT
    captured = DriverSettings.capture(settings, _PARAMETER_KEYS, DRIVER_CONTROL_DEFAULTS)
    script_path = str(Path(script).resolve())
    _SETTINGS, _SCRIPT = captured, script_path

# Internal scheduling constants.
# Fraction of detected RAM the scheduler may reserve for solves; a workstation
# keeps room for its desktop and page cache.
_MEMORY_HEADROOM = 0.90
# Dense: whole-estimate margin. Compressed: sampled operator margin only.
_MEMORY_SAFETY = 1.35
_MAX_PANELS = 100_000
# Pool workers are replaced after this many units so allocator growth from a
# big solve cannot accumulate across a long sweep (a respawn costs about half
# a second of imports and cold hashing, 60 ms per unit at this interval).
_TASKS_PER_CHILD = 8
_GEOMETRY_EXTS = (".geo",)

MANIFEST_SCHEMA = "ghost.local.2d-run.v3"
OUTPUT_POLARIZATIONS = ("VV", "HH")

# Parsed geometry snapshots reused by successive units in each spawned worker.
_SNAPSHOT_CACHE = {}  # type: Dict[str, Tuple[Dict[str, Any], str]]


def _solver_source_records() -> 'Tuple[str, Dict[str, str]]':
    backend_dir = str(_backend_root())
    return backend_dir, {'driver_configured.py': str(Path(_SCRIPT).resolve())}


def _solver_source_fingerprint() -> 'str':
    backend_dir, extra = _solver_source_records()
    return backend_source_fingerprint(backend_dir, extra)


def _solver_source_inventory() -> 'Dict[str, str]':
    backend_dir, extra = _solver_source_records()
    return backend_source_inventory(backend_dir, extra)


def _write_json_atomic(path: 'Path', payload: 'Dict[str, Any]') -> 'None':
    temporary = Path(str(path) + f".tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    os.replace(str(temporary), str(path))


def _verify_run_provenance(context):
    return verify_local_run_provenance(context, _solver_source_fingerprint, _solver_source_inventory)


def _unit_attestation_fields(context, unit):
    return unit_attestation_fields(context, unit, 'azimuths_deg', OUTPUT_POLARIZATIONS)


def _discover_geometries() -> 'List[Path]':
    found: 'List[Path]' = []
    seen: 'set' = set()
    for d in (_SETTINGS.FRD_DIR, _SETTINGS.OPN_DIR):
        root = Path(d)
        if not root.is_dir():
            print(f"  [warn] dir not found: {root}", file=sys.stderr)
            continue
        for ext in _GEOMETRY_EXTS:
            for p in sorted(root.rglob(f"*{ext}")):
                rp = p.resolve()
                if rp in seen:
                    continue
                seen.add(rp)
                found.append(p)
    return found


def _geometry_role(path: 'Path') -> 'str':
    resolved = Path(path).resolve()
    for role, directory in (("FRD", _SETTINGS.FRD_DIR), ("OPN", _SETTINGS.OPN_DIR)):
        try:
            resolved.relative_to(Path(directory).resolve())
            return role
        except ValueError:
            continue
    raise ValueError(f"Geometry is outside configured input folders: {path}")


def _unit_name(unit: 'Dict[str, Any]') -> 'str':
    return (f"{float(unit['frequency_ghz']):.3f}GHz_"
            f"{unit['geometry_stem']}.grim")


def _unit_output_path(results_dir: 'Path', unit: 'Dict[str, Any]') -> 'Path':
    role = str(unit.get("role", "")).strip().upper()
    folder = results_dir / role if role else results_dir
    return folder / _unit_name(unit)


def _load_snapshot(geometry_path: 'str') -> 'Tuple[Dict[str, Any], str]':
    """Load through the shared reader using this driver's process-local cache."""
    return load_geometry_snapshot(geometry_path, _SNAPSHOT_CACHE)


def _pool_initializer(blas_threads: 'int', settings=None, script=None) -> 'None':
    if settings is not None:
        # Spawned workers import this module fresh; restore the run's settings.
        configure(settings, script=script)
    hpc_scheduler.pin_blas_threads(blas_threads)
    hpc_scheduler.install_fingerprint_cache()
    import ghost_backend.twod.solver as rcs_solver

    rcs_solver.set_assembly_threads(1)


@unit_execution
def _solve_and_export(
    unit: 'Dict[str, Any]',
    context: 'Dict[str, Any]',
    results_dir_str: 'str',
) -> 'Tuple[str, str]':
    """Run the shared 2D pipeline using this driver's paths and verifiers."""
    adapter = WorkerAdapter(
        _unit_output_path, _verify_run_provenance, _verify_unit_input,
        _unit_attestation_fields, _load_snapshot, 'run_local_monostatic.py',
        record_memory=_record_memory_evidence)
    return run_twod_unit(unit, context, results_dir_str, adapter)


def _record_memory_evidence(result, context, unit, peak_reset):
    return record_memory_evidence(result, context, unit, peak_reset, _unit_name)


def _solve_and_export_star(args: 'tuple') -> 'tuple':
    """Pool entry point: unpack args and catch exceptions in-band.

    The full traceback string is returned (not just str(exc)) so a failure
    names the line it happened on rather than only its message.  The unit's
    CPU reservation bounds its assembly threads, its CPU allocation and its
    BLAS team alike.
    """

    unit, context, results_dir_str, assembly_threads = args
    try:
        import ghost_backend.twod.solver as rcs_solver
        from ghost_backend.execution.thread_control import threadpool_limits
        cpus = max(1, int(assembly_threads))
        rcs_solver.set_assembly_threads(cpus)
        context = dict(context, execution_assembly_threads=cpus)
        with hpc_scheduler.cpu_allocation_scope(cpus), \
                threadpool_limits(limits=cpus, user_api="blas"):
            status, path = _solve_and_export(unit, context, results_dir_str)
        return ("ok", status, path)
    except Exception:
        return ("err", traceback.format_exc(), "")


def _plan(units, fine_factor, n_angles, records_out=None):
    """Share preparation across a geometry's frequencies and polarizations."""
    from ghost_backend.runs.batch import combine_channels
    grouped = {}
    for unit in units:
        grouped.setdefault(str(unit['geometry']), []).append(unit)
    costs, peaks = {}, {}
    batches = hpc_scheduler.predict_2d_resources_for_geometries(
        {geometry: sorted({float(u['frequency_ghz']) for u in group}) for geometry, group in grouped.items()},
        ['TM', 'TE'], _SETTINGS.GEOMETRY_UNITS, _MAX_PANELS, fine_factor=fine_factor,
        n_angles=n_angles, safety=_MEMORY_SAFETY, solver_method=AUTOMATIC_SOLVER_METHOD,
        workers=_SETTINGS.PLANNING_WORKERS)
    for geometry, group in grouped.items():
        batch = batches[geometry]
        for unit in group:
            name = _unit_name(unit)
            plans = [batch[(float(unit['frequency_ghz']), pol)] for pol in ('TM', 'TE')]
            record = dict(unit=name, **combine_channels(plans, n_angles, fine_factor))
            costs[name], peaks[name] = record['cost'], record['peak_gb']
            if records_out is not None:
                records_out.append(record)
    return costs, peaks


def _unit_assembly_threads(
    cores: 'int', pool_size: 'int', budget_gb: 'float', peak_gb: 'float'
) -> 'int':
    """Thread count/CPU reservation derived from this unit's own footprint."""

    return hpc_scheduler.assembly_threads_for_unit(
        cores, pool_size, budget_gb, peak_gb, configured=current_options()['assembly_threads']
    )


def _validate_config() -> 'Tuple[List[float], List[float]]':
    if _SETTINGS.ACCURACY_TARGET not in ("standard", "tight"):
        sys.exit("ERROR: ACCURACY_TARGET must be 'standard' or 'tight'.")
    if type(_SETTINGS.MESH_CERTIFICATION) is not bool:
        sys.exit("ERROR: MESH_CERTIFICATION must be True or False.")
    if not _SETTINGS.FREQUENCIES_GHZ: sys.exit("ERROR: FREQUENCIES_GHZ is empty.")
    if not _SETTINGS.AZIMUTHS_DEG:    sys.exit("ERROR: AZIMUTHS_DEG is empty.")
    frequencies = [float(value) for value in _SETTINGS.FREQUENCIES_GHZ]
    if (
        not all(math.isfinite(value) and value > 0.0 for value in frequencies)
        or len(set(frequencies)) != len(frequencies)
        or len({f"{value:.3f}" for value in frequencies}) != len(frequencies)
    ):
        sys.exit(
            "ERROR: frequencies must be finite, positive, unique, and "
            "distinct at the 0.001 GHz output-name precision."
        )
    azimuths = [float(value) for value in _SETTINGS.AZIMUTHS_DEG]
    if (
        not all(math.isfinite(value) for value in azimuths)
        or len(set(azimuths)) != len(azimuths)
    ):
        sys.exit("ERROR: AZIMUTHS_DEG must be finite and unique.")
    if str(_SETTINGS.GEOMETRY_UNITS).strip().lower() not in {"inches", "meters"}:
        sys.exit("ERROR: GEOMETRY_UNITS must be 'inches' or 'meters'.")
    if _SETTINGS.MAX_SOLVE_GB is not None and float(_SETTINGS.MAX_SOLVE_GB) <= 0.0:
        sys.exit("ERROR: MAX_SOLVE_GB must be positive or None.")
    if _SETTINGS.WORKERS is not None and int(_SETTINGS.WORKERS) < 1:
        sys.exit("ERROR: WORKERS must be a positive integer or None.")
    return frequencies, azimuths


def _freeze_runtime(run_dir):
    """Run this sweep from a frozen backend copy, as the HPC path does.

    Editing the checkout (or the driver script) while a local sweep runs would
    otherwise fail every remaining unit's provenance check. The snapshot costs
    about a second and a few MB per run.
    """
    global _SCRIPT, _backend_root
    from ghost_backend.hpc.runtime_snapshot import snapshot_backend_runtime
    import shutil
    runtime_parent = snapshot_backend_runtime(_backend_root(), run_dir)
    staged = Path(run_dir) / "driver_configured.py"
    shutil.copy2(_SCRIPT, staged)
    _SCRIPT = str(staged)
    frozen_backend = Path(runtime_parent) / "ghost_backend"
    _backend_root = lambda: frozen_backend
    # Spawned solve workers inherit sys.path and import the frozen copy.
    sys.path.insert(0, str(runtime_parent))


@driver_execution
def main() -> 'None':
    frequencies, azimuths = _validate_config()
    if _SETTINGS.MAX_SOLVE_GB:
        # Read by the solver's own memory gate, in this process and every
        # forked worker.
        os.environ["GHOST_MAX_SOLVE_GB"] = f"{float(_SETTINGS.MAX_SOLVE_GB):g}"
    blas_threads = blas_thread_reservation()
    hpc_scheduler.pin_blas_threads(blas_threads)
    hpc_scheduler.install_fingerprint_cache()

    geometries = _discover_geometries()
    if not geometries:
        sys.exit("ERROR: no geometry files (*.geo) found under FRD_DIR or OPN_DIR.")
    stems = [geometry.stem for geometry in geometries]
    if len(stems) != len(set(stems)):
        sys.exit(
            "ERROR: geometry stems must be unique; output names would "
            "otherwise collide."
        )

    units: 'List[Dict[str, Any]]' = []
    from ghost_backend.assembly.fields import geometry_input_fingerprint
    for geom in geometries:
        input_fingerprint = geometry_input_fingerprint(
            str(geom), _SETTINGS.GEOMETRY_UNITS
        )
        for f in frequencies:
            # The azimuth grid is deliberately NOT repeated per unit: it is
            # identical for every unit in the run and is bound by hash.
            units.append({
                "geometry":      str(geom.resolve()),
                "geometry_stem": geom.stem,
                "geometry_input_sha256": input_fingerprint,
                "role":          _geometry_role(geom),
                "polarizations": list(OUTPUT_POLARIZATIONS),
                "frequency_ghz": float(f),
            })

    mesh_policy = accuracy_target_policy(_SETTINGS.ACCURACY_TARGET)
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")
    run_dir     = Path(_SETTINGS.OUTPUT_DIR).resolve() / run_id
    results_dir = run_dir / "results"
    run_dir.mkdir(parents=True, exist_ok=False)
    _freeze_runtime(run_dir)
    results_dir.mkdir()
    (results_dir / "FRD").mkdir()
    (results_dir / "OPN").mkdir()
    solver_config = {
        "geometry_units": _SETTINGS.GEOMETRY_UNITS,
        "linear_solver": "dense_lu",
        "polarizations": list(OUTPUT_POLARIZATIONS),
        "max_panels": _MAX_PANELS,
        "blas_threads_per_worker": blas_threads,
        "mesh_convergence_policy": mesh_policy,
        "accuracy_target": _SETTINGS.ACCURACY_TARGET,
        "lu_precision": AUTOMATIC_LU_PRECISION,
        "solver_method": AUTOMATIC_SOLVER_METHOD,
        "execution_options": current_options(),
        "mesh_certification": bool(_SETTINGS.MESH_CERTIFICATION),
    }
    manifest: 'Dict[str, Any]' = {
        "schema": MANIFEST_SCHEMA,
        "status": "running",
        "run_id": run_id,
        "created": datetime.now().isoformat(),
        "frequencies_ghz": frequencies,
        "azimuths_deg": azimuths,
        "polarizations": list(OUTPUT_POLARIZATIONS),
        "n_units": len(units),
        "solver_source_sha256": _solver_source_fingerprint(),
        # Per-file hashes behind that fingerprint, so a later mismatch can say
        # which file moved instead of only that one did.
        "solver_source_inventory": _solver_source_inventory(),
        "runtime_environment_sha256": runtime_environment_fingerprint(),
        "submission_runtime_environment": runtime_environment_payload(),
        "solver_config": solver_config,
        "units": units,
    }
    manifest_path = run_dir / "manifest.json"
    _write_json_atomic(manifest_path, manifest)

    # Resolve shared manifest fields once in the parent process.
    context = {
        "run_id": run_id,
        "solver_source_sha256": manifest["solver_source_sha256"],
        "solver_source_inventory": manifest["solver_source_inventory"],
        "runtime_environment_sha256": manifest["runtime_environment_sha256"],
        "submission_runtime_environment": manifest.get("submission_runtime_environment"),
        "run_solve_spec_sha256": manifest_solve_spec_fingerprint(manifest),
        "solver_config_sha256": stable_json_fingerprint(solver_config),
        "geometry_units": _SETTINGS.GEOMETRY_UNITS,
        "max_panels": _MAX_PANELS,
        "mesh_convergence_policy": mesh_policy,
        "lu_precision": AUTOMATIC_LU_PRECISION,
        "solver_method": AUTOMATIC_SOLVER_METHOD,
        "execution_options": current_options(),
        "mesh_certification": bool(_SETTINGS.MESH_CERTIFICATION),
        "azimuths_deg": azimuths,
        "angular_grid_sha256": stable_json_fingerprint(
            azimuths
        ),
    }

    # Cost every unit from the real mesh, then run dearest-first: a frequency
    # sweep's cost spread is large (it grows like the square of the node
    # count), and starting with the cheap end leaves the expensive tail with
    # nothing to overlap against.
    fine_factor = (
        float(mesh_policy["fine_factor"]) if _SETTINGS.MESH_CERTIFICATION else 1.0
    )
    planning_records = []
    costs, peaks = _plan(units, fine_factor, len(azimuths), planning_records)
    # Sorted into a new list, never in place: `units` is the same object the
    # manifest holds, and reordering it after the run fingerprint was taken
    # would make the manifest on disk hash differently from what every
    # attestation recorded.
    ordered = sorted(
        units, key=lambda u: (-costs.get(_unit_name(u), 1.0), _unit_name(u))
    )

    cores = hpc_scheduler.detect_cores()
    blas_cap = hpc_scheduler.blas_thread_cap(cores)
    if blas_threads > cores:
        raise ValueError("BLAS threads per solve exceed the available CPU allocation ({}).".format(cores))
    # GiB throughout, like the planner's peaks; capped by what the desktop
    # leaves available when the sweep starts.
    budget_gb, memory_gb, available_gb = hpc_scheduler.local_memory_budget_gb(
        _MEMORY_HEADROOM
    )
    if budget_gb <= 0:
        raise MemoryError('No RAM is currently available for the local solve reservation.')
    worker_cap = max(1, cores - 1) if _SETTINGS.WORKERS is None else int(_SETTINGS.WORKERS)
    pool_size = max(1, min(cores, worker_cap, len(ordered)))
    from ghost_backend.runs.batch import apply_batch_choices
    resolved, batch_selections, batch_summary = apply_batch_choices(
        planning_records, cores, pool_size, budget_gb, current_options())
    for record in resolved:
        costs[record['unit']], peaks[record['unit']] = record['cost'], record['peak_gb']
    ordered = sorted(units, key=lambda u: (-costs[_unit_name(u)], _unit_name(u)))
    _write_json_atomic(run_dir / 'schedule.json', dict(units=resolved, batch_selection=batch_summary))
    heaviest = max((peaks.get(_unit_name(u), 0.0) for u in ordered), default=0.0)
    heaviest_concurrency = (
        pool_size if heaviest <= 0.0
        else max(1, min(pool_size, int(budget_gb // heaviest)))
    )
    unit_thread_counts = [
        _unit_assembly_threads(
            cores, pool_size, budget_gb, peaks.get(_unit_name(unit), 0.0)
        )
        for unit in ordered
    ] or [1]
    min_threads = min(unit_thread_counts)
    max_threads = max(unit_thread_counts)
    thread_label = (
        str(min_threads) if min_threads == max_threads
        else f"{min_threads}-{max_threads} dynamic"
    )

    print("=" * 70)
    print("Local monostatic RCS sweep")
    print("=" * 70)
    print(f"  Run dir       : {run_dir}")
    print(f"  Geometries    : {len(geometries)}")
    print("  Polarizations : VV, HH (co-solved)")
    print(f"  Frequencies   : {len(_SETTINGS.FREQUENCIES_GHZ)}  "
          f"({min(_SETTINGS.FREQUENCIES_GHZ):g}-{max(_SETTINGS.FREQUENCIES_GHZ):g} GHz)")
    print(f"  Azimuths      : {len(_SETTINGS.AZIMUTHS_DEG)}")
    print(f"  Units total   : {len(ordered)}  (geometry x frequency)")
    print(f"  Mesh check    : {'base + fine comparison' if _SETTINGS.MESH_CERTIFICATION else 'base only (no mesh comparison)'}")
    print(f"  Run policy    : {run_control_summary(current_options(), _SETTINGS.MESH_CERTIFICATION)}")
    if _SETTINGS.MESH_STRATEGY == 'adaptive' and _SETTINGS.BASIS_ORDER != 1:
        print(f"  Order note    : requested P{_SETTINGS.BASIS_ORDER} is ignored; adaptive controls polynomial order.")
    print(f"  Workers       : {pool_size} of {cores} cpus  "
          f"(CPU reservation per solve, assembly and BLAS alike; BLAS team at most {blas_cap}, "
          f"assembly threads/solve: {thread_label})")
    if heaviest_concurrency < pool_size:
        print(f"  Heaviest units: {heaviest_concurrency} concurrent at "
              f"{heaviest:.1f} GB each; smaller units expand dynamically")
    available_text = (f", {available_gb:.1f} GiB available"
                      if available_gb is not None else "")
    print(f"  Memory        : {memory_gb:.1f} GiB installed{available_text}, "
          f"{budget_gb:.1f} GiB schedulable")
    if not _SETTINGS.MESH_CERTIFICATION:
        print("  Mesh comparison is off: downstream use remains enabled; the")
        print("  user owns the mesh-resolution decision.")
    print("=" * 70, flush=True)

    counters = {"written": 0, "skipped": 0, "failed": 0}
    started = time.time()
    total = len(ordered)

    def _prepare(unit):
        name = _unit_name(unit)
        peak_gb = peaks.get(name, 0.0)
        assembly_threads = reservations.get(name) or _unit_assembly_threads(
            cores, pool_size, budget_gb, peak_gb
        )
        return (
            name, peak_gb,
            (_solve_and_export_star,
             ((unit, dict(context, batch_backend_selection=batch_selections.get(name),
                          forecast_peak_gib=peak_gb),
               str(results_dir), assembly_threads),)),
        )

    def _finished():
        return counters["written"] + counters["skipped"] + counters["failed"]

    def _on_result(name, payload):
        kind, first, _second = payload
        if kind == "ok":
            counters["skipped" if first == "skipped" else "written"] += 1
            print(f"  [{_finished():4d}/{total}] {first:7s}  {name}", flush=True)
        else:
            counters["failed"] += 1
            print(f"  [{_finished():4d}/{total}] FAILED   {name}", flush=True)
            for line in str(first).rstrip().splitlines():
                print(f"      {line}", flush=True)

    def _on_error(name, exc):
        counters["failed"] += 1
        print(f"  [{_finished():4d}/{total}] FAILED (dispatch) {name}: {exc!r}",
              flush=True)

    # Ordinary spawned workers can run compressed tile processes; unlike a
    # daemon Pool they also report native worker death to the dispatcher.
    # Import after the launch environment has pinned native thread pools.
    from ghost_backend.hpc.common import ExecutorPool
    # One CPU reservation per unit (fill rule or cost-proportional share,
    # whichever is larger); workers inherit the node's BLAS pool size and each
    # unit limits its own BLAS team to its reservation.
    reservations = hpc_scheduler.cpu_reservations(
        [(_unit_name(u), costs.get(_unit_name(u), 1.0), peaks.get(_unit_name(u), 0.0)) for u in ordered],
        cores, pool_size, budget_gb, configured=current_options()["assembly_threads"])
    hpc_scheduler.pin_blas_threads(blas_cap)
    try:
        with ExecutorPool(
            processes=pool_size,
            initializer=_pool_initializer,
            initargs=(blas_cap, current_settings(), _SCRIPT),
            max_tasks_per_child=_TASKS_PER_CHILD,
        ) as pool:
            dispatcher = hpc_scheduler.MemoryAwareDispatcher(
                pool, budget_gb=budget_gb, max_concurrent=pool_size,
                cpu_budget=cores,
            )

            def _resources(unit):
                name = _unit_name(unit)
                peak_gb = peaks.get(name, 0.0)
                return (
                    peak_gb,
                    reservations.get(name) or max(blas_threads, _unit_assembly_threads(
                        cores, pool_size, budget_gb, peak_gb
                    )),
                )

            dispatcher.run(
                ordered, _prepare, _on_result, _on_error, _resources
            )
    except BaseException as exc:
        # The manifest must not claim a stopped sweep is still running.
        manifest["status"] = (
            "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        )
        _write_json_atomic(manifest_path, manifest)
        raise

    elapsed = time.time() - started
    print(f"\n  Done. wrote={counters['written']}, "
          f"skipped={counters['skipped']}, failed={counters['failed']}.  "
          f"{elapsed:.1f} s elapsed.")
    print(f"  Outputs: {results_dir}/")
    manifest["status"] = "failed" if counters["failed"] else "complete"
    _write_json_atomic(manifest_path, manifest)
    if counters["failed"]:
        raise SystemExit(1)



def load_default_settings():
    """Configure from the canonical run_local_monostatic.py parameters (programmatic use and tests)."""
    import importlib
    defaults = importlib.import_module("ghost_backend.run_local_monostatic")
    configure(vars(defaults), script=defaults.__file__)


def run(namespace, script):
    """Entry point used by the user-facing run_local_monostatic.py parameter script."""
    configure(namespace, script=script)
    main()


def __getattr__(name):
    """Keep reads of configured parameter attributes compatible with old callers."""
    if name in _SETTINGS:
        return _SETTINGS[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
