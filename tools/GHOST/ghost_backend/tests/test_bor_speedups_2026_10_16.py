"""Regression tests for the 16 October 2026 BoR speedups.

Each speedup keeps its reference path behind an internal switch; these tests
pin the new path against it (bitwise or to rounding) and pin the lifecycle of
the persistent near-preparation process pool.
"""
import multiprocessing
import os
import subprocess
import sys
import textwrap
import time
from concurrent.futures import ProcessPoolExecutor
from unittest import mock

import numpy as np
import pytest

import ghost_backend.bor.solver as B
from ghost_backend.bor import near_parallel as NP

THETAS = list(np.linspace(0.0, 180.0, 25))


def _peak_relative(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return float(np.max(np.abs(a - b)) / max(float(np.max(np.abs(a))), 1e-300))


def _fields(result):
    return np.array([result['amp_vv'], result['amp_hh']])


# ------------------------------------------------------------- S-5 test basis

@pytest.mark.parametrize('gauss_order', [1, 2, 3, 4, 6])
@pytest.mark.parametrize('columns', [2, 3, 64, 129])
@pytest.mark.parametrize('transposed', [False, True])
def test_order_loop_test_accumulation_is_bitwise(monkeypatch, gauss_order, columns, transposed):
    solver = B.BorPecSolver(B.sphere_generatrix(0.1, 37), 3e9, gauss_order=gauss_order)
    rng = np.random.default_rng(gauss_order * 1000 + columns)
    shape = (columns, solver.P) if transposed else (solver.P, columns)
    values = rng.standard_normal(shape) + 1j * rng.standard_normal(shape)
    values = values.T if transposed else values
    values[::5] = -0.0
    monkeypatch.setattr(B, '_TEST_ACCUMULATE_ORDER_LOOP', False)
    reference = solver._test_accumulate(values)
    monkeypatch.setattr(B, '_TEST_ACCUMULATE_ORDER_LOOP', True)
    new = solver._test_accumulate(values)
    assert new.dtype == reference.dtype and new.shape == reference.shape
    assert np.array_equal(new.view(np.uint64), reference.view(np.uint64))
    # Real point values and the 1-D path (reference reduction) as well.
    real = rng.standard_normal((solver.P, columns))
    monkeypatch.setattr(B, '_TEST_ACCUMULATE_ORDER_LOOP', False)
    real_ref, vector_ref = solver._test_accumulate(real), solver._test_accumulate(real[:, 0])
    monkeypatch.setattr(B, '_TEST_ACCUMULATE_ORDER_LOOP', True)
    assert np.array_equal(solver._test_accumulate(real).view(np.uint64), real_ref.view(np.uint64))
    assert np.array_equal(solver._test_accumulate(real[:, 0]), vector_ref)


def test_batched_excitation_is_bitwise_with_the_order_loop(monkeypatch):
    solver = B.BorPecSolver(B.sphere_generatrix(0.1, 50), 4e9)
    out = {}
    for flag in (False, True):
        monkeypatch.setattr(B, '_TEST_ACCUMULATE_ORDER_LOOP', flag)
        out[flag] = [solver.rhs_vv_hh_batch(m, THETAS, efie_scale=0.5, mfie_scale=0.5 * B.ETA0)
                     for m in (0, 1, -3, 7)]
    for a, b in zip(out[False], out[True]):
        assert np.array_equal(a, b)


# ------------------------------------------------------ S-2 far field by reciprocity

def _batch_far_fields(monkeypatch, solver, m, solutions, **kwargs):
    fields = {}
    for flag in (False, True):
        monkeypatch.setattr(B, '_FARFIELD_RECIPROCITY', flag)
        solver.rhs_vv_hh_batch(m, THETAS, efie_scale=1.0)
        fields[flag] = solver.farfield_vv_hh_batch(m, solutions, THETAS, **kwargs)
    return fields


@pytest.mark.parametrize('m', [0, 1, -2, 9])
@pytest.mark.parametrize('kind', ['pec', 'uniform_ibc', 'magnetic'])
def test_reciprocal_batch_far_field_matches_the_projection(monkeypatch, m, kind):
    solver = B.BorPecSolver(B.sphere_generatrix(0.1, 45), 3.5e9)
    rng = np.random.default_rng(abs(m) + 11)
    shape = (2 * solver.Nn, 2 * len(THETAS))
    solutions = rng.standard_normal(shape) + 1j * rng.standard_normal(shape)
    kwargs = {}
    if kind == 'uniform_ibc':
        kwargs['zs_pt'] = np.full(solver.P, 120.0 + 60.0j)
    elif kind == 'magnetic':
        kwargs['msolutions'] = rng.standard_normal(shape) + 1j * rng.standard_normal(shape)
    fields = _batch_far_fields(monkeypatch, solver, m, solutions, **kwargs)
    assert _peak_relative(fields[False], fields[True]) <= 1e-13
    # The retained radiation vectors are consumed with the batch.
    assert not any(key[0] == 'radiation' for key in solver._angular_local.batches
                   if isinstance(key, tuple) and key and isinstance(key[0], str))


def test_varying_impedance_and_missing_excitation_keep_the_projection(monkeypatch):
    solver = B.BorPecSolver(B.sphere_generatrix(0.1, 30), 3e9)
    rng = np.random.default_rng(3)
    shape = (2 * solver.Nn, 2 * len(THETAS))
    solutions = rng.standard_normal(shape) + 1j * rng.standard_normal(shape)
    zs = np.linspace(80 + 20j, 200 + 90j, solver.P)
    fields = _batch_far_fields(monkeypatch, solver, 2, solutions, zs_pt=zs)
    assert np.array_equal(fields[False], fields[True])
    # Without a preceding excitation of the same aspects the projection runs.
    monkeypatch.setattr(B, '_FARFIELD_RECIPROCITY', True)
    solver._angular_local.batches = {}
    alone = solver.farfield_vv_hh_batch(2, solutions, THETAS)
    monkeypatch.setattr(B, '_FARFIELD_RECIPROCITY', False)
    solver._angular_local.batches = {}
    assert np.array_equal(alone, solver.farfield_vv_hh_batch(2, solutions, THETAS))


_SOLVES = {
    'pec_cfie': lambda: B.solve_bor(B.sphere_generatrix(0.1, 40), 3e9, THETAS, formulation='cfie'),
    'pec_efie': lambda: B.solve_bor(B.sphere_generatrix(0.1, 40), 3e9, THETAS, formulation='efie'),
    'ibc': lambda: B.solve_bor(B.sphere_generatrix(0.1, 40), 3e9, THETAS, zs=120 + 60j),
    'ibc_taper': lambda: B.solve_bor(B.sphere_generatrix(0.1, 40), 3e9, THETAS, formulation='efie',
                                     zs=np.linspace(80 + 20j, 200 + 90j, 40)),
    'dielectric': lambda: B.solve_bor_dielectric(B.sphere_generatrix(0.1, 30), 2e9, THETAS,
                                                 eps_r=3 - 0.1j, mu_r=1 - 0.02j),
    'coated': lambda: B.solve_bor_coated_pec(B.sphere_generatrix(0.12, 30), B.sphere_generatrix(0.08, 24),
                                             2e9, THETAS, eps_r=3 - 0.1j, mu_r=1 - 0.02j),
    'coated2': lambda: B.solve_bor_coated2_pec(B.sphere_generatrix(0.13, 30), B.sphere_generatrix(0.11, 26),
                                               B.sphere_generatrix(0.08, 22), 2e9, THETAS,
                                               eps_inner=4.0 - 0.2j, mu_inner=1.0,
                                               eps_outer=2.5 - 0.05j, mu_outer=1.0),
}


@pytest.mark.parametrize('name', sorted(_SOLVES))
def test_whole_solves_match_the_reference_far_field_and_test_basis(monkeypatch, name):
    fields = {}
    for flag in (False, True):
        monkeypatch.setattr(B, '_FARFIELD_RECIPROCITY', flag)
        monkeypatch.setattr(B, '_TEST_ACCUMULATE_ORDER_LOOP', flag)
        fields[flag] = _fields(_SOLVES[name]())
    assert _peak_relative(fields[False], fields[True]) <= 1e-12


# ------------------------------------------------------------ S-1 pool lifecycle

def _alive(pid):
    import psutil
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.Error:
        return False


def _wait_dead(pids, seconds=60.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not any(_alive(pid) for pid in pids):
            return True
        time.sleep(0.2)
    return False


@pytest.fixture
def clean_pool():
    NP.close_near_process_pool()
    yield
    NP.close_near_process_pool()


def test_persistent_pool_is_reused_resized_and_closed(clean_pool):
    from ghost_backend.execution.runtime import SINGLE_THREAD_WORKER_ENVIRONMENT
    environment = {name: os.environ.get(name) for name, _ in SINGLE_THREAD_WORKER_ENVIRONMENT}
    executor, existed = NP._acquire_persistent(2)
    assert not existed
    pids = NP.near_process_pool_info()['pids']
    assert len(pids) == 2
    # Every worker is spawned up front, so the parent's environment is not
    # pinned for the pool's lifetime.
    assert not NP._PERSISTENT['pinned']
    again, existed = NP._acquire_persistent(2)
    assert existed and again is executor
    assert NP.near_process_pool_info()['uses'] == 2
    assert executor.submit(NP._worker_started).result(timeout=60) in pids
    resized, existed = NP._acquire_persistent(3)
    assert not existed and resized is not executor
    assert _wait_dead(pids)
    new_pids = NP.near_process_pool_info()['pids']
    NP.close_near_process_pool()
    assert not NP.near_process_pool_info()['alive']
    assert _wait_dead(new_pids)
    assert environment == {name: os.environ.get(name) for name in environment}


def test_scope_keeps_used_pool_and_releases_unused_failed_or_mismatched(clean_pool):
    with mock.patch.object(NP, 'process_backend_possible', return_value=True), \
            mock.patch.object(NP, 'processes_selected', return_value=True):
        with NP.process_scope(2, 2) as state:
            first = NP.executor_for(10_000, 10)
        assert first is not None and not state['reused']
        assert NP.near_process_pool_info()['alive']          # kept for the next preparation
        with NP.process_scope(2, 2, prewarm=True) as state:
            assert state['prewarmed'] and state['reused']
            assert NP.executor_for(10_000, 10) is first
        pids = NP.near_process_pool_info()['pids']
        # A preparation admitted for another size releases it on entry.
        with NP.process_scope(3, 3) as state:
            assert not NP.near_process_pool_info()['alive']
        assert _wait_dead(pids)
        # A preparation that did not use its pool releases it.
        with NP.process_scope(2, 2, prewarm=True):
            pass
        assert not NP.near_process_pool_info()['alive']
        # A failure (or cancellation) releases it.
        with pytest.raises(RuntimeError):
            with NP.process_scope(2, 2):
                NP.executor_for(10_000, 10)
                raise RuntimeError('cancelled')
        assert not NP.near_process_pool_info()['alive']


def test_far_compression_pool_releases_the_idle_near_pool(clean_pool):
    from ghost_backend.bor import compressed_far as CF
    NP._acquire_persistent(2)
    with mock.patch.object(CF, '_process_workers', return_value=2):
        geometry = mock.Mock(work_bytes=1.0)
        executor = CF._Executor(geometry, 2, CF.FAR_COMPRESSION_PROCESS_PAIRS)
    try:
        assert executor.backend == 'processes'
        assert not NP.near_process_pool_info()['alive']
    finally:
        executor.close()


def _driver_unit_with_pool():
    """A driver unit (concurrent.futures worker) whose solve kept a pool."""
    from ghost_backend.bor import near_parallel
    near_parallel._acquire_persistent(2)
    return near_parallel.near_process_pool_info()['pids'], os.getpid()


def test_driver_worker_with_max_tasks_per_child_exits_and_reaps_its_pool():
    context = multiprocessing.get_context('spawn')
    with ProcessPoolExecutor(1, mp_context=context, max_tasks_per_child=1) as pool:
        pids, worker = pool.submit(_driver_unit_with_pool).result(timeout=120)
        assert len(pids) == 2
        # The retiring worker must exit (it joins its children) and take the
        # idle pool with it; a second unit then runs in a fresh worker.
        pids2, worker2 = pool.submit(_driver_unit_with_pool).result(timeout=120)
        assert worker2 != worker
        assert _wait_dead([worker] + pids)
    assert _wait_dead([worker2] + pids2)


def test_killed_parent_leaves_no_orphan_pool_workers(tmp_path):
    script = tmp_path / 'owner.py'
    script.write_text(textwrap.dedent('''
        import sys, time
        from ghost_backend.bor import near_parallel
        if __name__ == '__main__':
            near_parallel._acquire_persistent(2)
            print(' '.join(map(str, near_parallel.near_process_pool_info()['pids'])), flush=True)
            time.sleep(600)
    '''))
    owner = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.PIPE, text=True,
                             env=dict(os.environ))
    try:
        pids = [int(pid) for pid in owner.stdout.readline().split()]
        assert len(pids) == 2
        time.sleep(1.0)
        owner.kill()
        owner.wait(timeout=30)
        assert _wait_dead(pids)
    finally:
        if owner.poll() is None:
            owner.kill()


# --------------------------------------------------------- admission of the idle pool

def test_mode_phase_admission_charges_the_idle_pool():
    with mock.patch('ghost_backend.bor.near_parallel.process_backend_possible', return_value=True), \
            mock.patch('ghost_backend.execution.options.allocated_cpu_budget', return_value=8), \
            mock.patch('ghost_backend.execution.options.physical_core_count', return_value=8):
        plan = B.plan_bor_mode_workers(800, 600, 4, 30, 0.5, memory_limit_gb=64.0, near_pairs=10_000)
    near = plan['near_preparation']
    assert near['process_overhead_bytes_per_worker'] > 0
    assert near['persistent_pool_idle_gb'] == pytest.approx(
        near['process_workers'] * NP.PROCESS_IDLE_BYTES / 1e9)
    mode_phase = B.estimate_bor_total_peak_gb(0.5 + near['persistent_pool_idle_gb'], plan['linear_peak_gb'])
    assert plan['estimated_peak_gb'] >= mode_phase
    without = B._guard_bor_dense_memory(800, 600, 4, 30, assembly_peak_gb=0.5)
    with_pool = B._guard_bor_dense_memory(800, 600, 4, 30, assembly_peak_gb=0.5, resident_pool_gb=1.0)
    assert with_pool > without


# ------------------------------------------------------- S-3 measured memory constants

def test_near_memory_constants_keep_the_measured_margin():
    # Measured 16 Oct 2026 (see the comments at the constants): a near task grew
    # a worker's RSS by at most 110 MB (exact allocation peak 137 MiB); an idle
    # pool worker held 69 MB RSS.
    measured_rss_growth, measured_peak, measured_worker = 110e6, 137 * 2**20, 69e6
    assert B._NEAR_TASK_SCRATCH_BYTES >= 1.5 * measured_rss_growth
    assert B._NEAR_TASK_SCRATCH_BYTES >= 1.3 * measured_peak
    assert B._NEAR_TASK_SCRATCH_BYTES >= B.NEAR_BATCH_KERNEL_BYTES + B.NEAR_KERNEL_WORK_BYTES
    assert NP.PROCESS_OVERHEAD_BYTES >= 1.5 * measured_worker
    assert NP.PROCESS_IDLE_BYTES >= 1.5 * measured_worker


# ------------------------------------------- A-BF-9 material solvers stream under auto

@pytest.mark.parametrize('name', ['dielectric', 'coated'])
def test_material_solvers_stream_under_auto_and_match_tables(name):
    thetas = THETAS[::3]
    if name == 'dielectric':
        def solve(assembly):
            return B.solve_bor_dielectric(B.sphere_generatrix(0.1, 30), 2e9, thetas, eps_r=3 - 0.1j,
                                          mu_r=1 - 0.02j, assembly=assembly)
    else:
        def solve(assembly):
            return B.solve_bor_coated_pec(B.sphere_generatrix(0.12, 30), B.sphere_generatrix(0.08, 24), 2e9,
                                          thetas, eps_r=3 - 0.1j, mu_r=1 - 0.02j, assembly=assembly)
    auto, tables = solve('auto'), solve('tables')
    assert auto['assembly'] == 'streaming' and tables['assembly'] == 'tables'
    assert _peak_relative(_fields(tables), _fields(auto)) <= 1e-12


def test_preview_prices_the_streamed_material_assembly():
    from ghost_backend.bor.dispatch import _direct_dense_plan
    thetas = list(np.linspace(0, 180, 19))
    plan = _direct_dense_plan(dict(points=B.sphere_generatrix(0.1, 30), freq_hz=2e9, thetas_deg=thetas,
                                   eps_r=3 - 0.1j, assembly='auto'), [(30, False, True)], 12, B.FAR_GAUSS_ORDER)
    assert plan['assumed_assembly'] == 'streaming'


# -------------------------------------------- A-BF-1 vectorized sincos in the samplers

def test_native_far_samplers_match_the_numpy_reference():
    from ghost_backend.bor import streaming as S
    if S._NATIVE is None or not hasattr(S._NATIVE, 'sample_brackets_pairs'):
        pytest.skip('native pair samplers unavailable')
    blocks = {}
    for native in (True, False):
        with mock.patch.object(S, '_NATIVE', S._NATIVE if native else None):
            for medium in (None, (3 - 0.4j, 1 - 0.05j)):
                solver = B.BorPecSolver(B.sphere_generatrix(0.1, 60), 4e9, medium=medium)
                solver.enable_streaming(8, efie=True, mfie=medium is None, pmchwt=medium is not None)
                solver.prepare_operators(8, efie=True, mfie=medium is None, ibc=medium is not None)
                for m in (0, 3, 8):
                    blocks[(native, medium is None, m, 'T')] = np.asarray(solver.assemble_mode(m, 8))
                    blocks[(native, medium is None, m, 'K')] = np.asarray(
                        solver.assemble_mfie_mode(m, 8) if medium is None else solver.assemble_pmchwt_P(m, 8))
                solver.close_streaming()
    for key, value in blocks.items():
        if key[0]:
            # The libm kernel shipped before October 16 differs from the NumPy
            # sampler by up to 3.9e-13 here (lossy rotated-PV family); the
            # vectorized one moves the far blocks by 2.6e-16 against it.
            # Patching the library out also switches the near kernels to
            # NumPy; since every self/adjacent pair uses the polar rule
            # (closer samples than the former cells) their rounding
            # difference on the self-node entries is 1.3e-12.
            assert _peak_relative(blocks[(False,) + key[1:]], value) <= 2e-12, key


def test_vector_and_portable_pair_samplers_are_bitwise_equal():
    import ctypes
    from ghost_backend.bor import streaming as S
    lib = S._NATIVE
    if lib is None or not hasattr(lib, 'ghost_set_pair_sampler_isa'):
        pytest.skip('kernel built before the vectorized samplers')
    select = lib.ghost_set_pair_sampler_isa
    select.argtypes, select.restype = [ctypes.c_int], ctypes.c_int
    rng = np.random.default_rng(5)
    npair, nxi = 37, 65
    geometry = [np.ascontiguousarray(rng.uniform(0.01, 0.3, npair)) for _ in range(8)]
    xi = np.linspace(-np.pi, 0.0, nxi)
    tables = [np.ascontiguousarray(t) for t in (np.sin(xi / 2) ** 2, np.cos(xi), np.sin(xi))]
    dp = lambda a: a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    results = {}
    try:
        for mode in (1, 0):
            select(mode)
            outs = []
            for kr, ki in ((140.0, 0.0), (140.0, -9.0)):
                g = np.empty((npair, 2 * nxi))
                lib.sample_g_pairs(npair, nxi, *[dp(geometry[i]) for i in (0, 1, 4, 5)], kr, ki,
                                   dp(tables[0]), dp(g), 1)
                outs.append(g)
                for family in (0, 1):
                    o = [np.empty((npair, 2 * nxi)) for _ in range(4)]
                    lib.sample_brackets_pairs(family, npair, nxi, *map(dp, geometry), kr, ki,
                                              dp(tables[1]), dp(tables[2]), *map(dp, o), 1)
                    outs.extend(o)
            results[mode] = outs
    finally:
        select(1)
    for a, b in zip(results[0], results[1]):
        assert np.array_equal(a, b)


# --------------------------------- certification: estimated error of the published mesh

def test_certified_bor_reports_the_published_error_estimate():
    from pathlib import Path
    from ghost_backend.bor.dispatch import solve_monostatic_rcs_bor_certified
    from ghost_backend.geometry.io import build_geometry_snapshot, parse_geometry
    from ghost_backend.runs.quality import solver_report_text
    geo = (Path(__file__).resolve().parents[1] / 'geometry' / 'geometries' / 'BOR'
           / 'pec_cylinder_r4_h10_in.geo')
    snapshot = build_geometry_snapshot(*parse_geometry(geo.read_text(encoding='utf-8-sig')))
    result = solve_monostatic_rcs_bor_certified(snapshot, [1.0], [0.0, 45.0, 90.0, 135.0, 180.0],
                                                geometry_units='inches', workers=2)
    mesh = result['metadata']['mesh_convergence']
    ratios = [fine / base for record in mesh['realized_mesh_refinement']
              for base, fine in zip(record['base_elements_by_surface'], record['fine_elements_by_surface'])]
    r = min(ratios)
    assert r > 1.0 and mesh['published_error_refinement_ratio'] == pytest.approx(r)
    for channel in ('VV', 'HH'):
        gate = mesh['polarizations'][channel]
        record = gate['estimated_published_error']
        assert record['available'] and record['assumed_order'] == 1.0
        assert record['refinement_ratio'] == pytest.approx(r)
        assert gate['estimated_published_complex_max_normalized'] == pytest.approx(
            gate['complex_max_normalized'] / (r - 1.0))
    worst = max(mesh['polarizations'][c]['estimated_published_complex_max_normalized'] for c in ('VV', 'HH'))
    text = solver_report_text(result['metadata'])
    assert 'Estimated error of the published (fine) result' in text
    assert f'{worst * 100.:.4g}%' in text
