"""Memory-only recovery preserves fixed backends, angles and worker limits."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from unittest.mock import patch

import numpy as np
import pytest
from ghost_backend.compressed import worker_pool
from ghost_backend.execution import angle_batch, frequency_sweep
from ghost_backend.execution.cpu import configured_batch_size
from ghost_backend.execution.options import current_options, validate_options
from ghost_backend.twod import solver
from general_fixtures import fixture
from test_adaptive_polynomial import wavelength_fixture
from test_experimental_cpu import fields


def forecast(*args, **kwargs):
    assert current_options()['factorization'] == 'compressed'
    return .1 + .01*configured_batch_size()


def test_default_recovers_before_assembly_without_picker_or_dense_retry():
    args = (fixture('rectangle', 24), [1.], list(range(361)))
    options = dict(ram_budget_gib=1, assembly_threads=2, blas_threads=2)
    with patch.object(solver, '_estimate_memory_gb', side_effect=forecast), \
         patch.object(solver, '_detect_available_gb', return_value=8.), \
         patch.object(worker_pool, 'release_idle', wraps=worker_pool.release_idle) as release, \
         patch('ghost_backend.execution.selection.select_backend', side_effect=AssertionError('picker')), \
         patch('ghost_backend.execution.timing_history.read', side_effect=AssertionError('history')), \
         patch('ghost_backend.twod.fields.DenseFactor', side_effect=AssertionError('dense retry')):
        result = solver.solve_monostatic_rcs_2d(*args, geometry_units='meters', execution_options=options)
        assert release.call_count == 1
        reference = solver.solve_monostatic_rcs_2d(*args, geometry_units='meters',
            execution_options=dict(options, factorization='compressed', angle_batch_size=64))
    metadata = result['metadata']
    assert metadata['execution_options']['factorization'] == 'compressed'
    assert metadata['execution_options']['angle_batch_size'] == 64
    assert metadata['experimental_cpu']['batch_size'] == 64
    assert 'backend_selection' not in metadata
    recovery = metadata['angle_batch_recovery'][0]
    assert recovery['admitted'] and recovery['n_angles'] == 361
    assert [a['batch'] for a in recovery['attempts']] == [256, 128, 64]
    assert all(a['budget_gib'] == 1 for a in recovery['attempts'])
    for pol in ('VV', 'HH'):
        assert len(result['co_solved_samples'][pol]) == 361
        np.testing.assert_allclose(fields(result, pol), fields(reference, pol), rtol=1e-10, atol=1e-12)
    assert angle_batch.limit() == 256 and current_options() is None


def test_refined_mesh_rechecks_memory_and_records_effective_batches():
    def price(*args, **kwargs):
        degree = kwargs['dense_resources'].get('basis_width', 2)-1
        return .1 + .01*configured_batch_size()*(4 if degree == 3 else 1)
    args = (wavelength_fixture(), [1.], list(range(361)))
    options = dict(ram_budget_gib=1, assembly_threads=2, blas_threads=2)
    with patch.object(solver, '_estimate_memory_gb', side_effect=price), \
         patch.object(solver, '_detect_available_gb', return_value=8.), \
         patch('ghost_backend.twod.adaptive_geometry.MIN_AUTOMATIC_REFERENCE_PANELS', 0), \
         patch('ghost_backend.execution.selection.select_backend', side_effect=AssertionError('picker')):
        result = solver.solve_monostatic_rcs_2d_certified(*args, geometry_units='meters', execution_options=options)
        reference = solver.solve_monostatic_rcs_2d_certified(*args, geometry_units='meters',
            execution_options=dict(options, angle_batch_size=16))
    metadata = result['metadata']
    assert metadata['mesh_convergence_certified']
    steps = metadata['adaptive_mesh']['steps']
    assert [s['angle_batch_size'] for s in steps[:2]] == [64, 16]
    assert all(s['backend'] == 'compressed' for s in steps)
    assert metadata['execution_options']['angle_batch_size'] == 16
    for pol in ('VV', 'HH'):
        assert len(result['co_solved_samples'][pol]) == 361
        np.testing.assert_allclose(fields(result, pol), fields(reference, pol), rtol=1e-10, atol=1e-12)


def test_oversized_operator_stops_at_one_and_restores_request_state():
    batches = []
    def price(*args, **kwargs):
        batches.append(configured_batch_size())
        return 2.
    with patch.object(solver, '_estimate_memory_gb', side_effect=price), \
         patch.object(solver, '_detect_available_gb', return_value=8.), \
         patch('ghost_backend.compressed.factor.CompressedFactor', side_effect=AssertionError('assembly started')):
        with pytest.raises(MemoryError, match='Current angle batch: 1'):
            solver.solve_monostatic_rcs_2d(fixture('rectangle', 24), [1.], list(range(361)),
                geometry_units='meters', execution_options=dict(ram_budget_gib=1))
    assert batches[-1] == 1 and len(batches) <= 10
    assert angle_batch.limit() == 256 and current_options() is None


def test_cancellation_during_recovery_stops_before_assembly():
    abort = threading.Event()
    def release():
        abort.set()
        return 0
    with patch.object(solver, '_estimate_memory_gb', side_effect=forecast), \
         patch.object(worker_pool, 'release_idle', side_effect=release), \
         patch.object(solver, '_detect_available_gb', return_value=8.):
        with pytest.raises(InterruptedError):
            solver.solve_monostatic_rcs_2d(fixture('rectangle', 24), [1.], list(range(361)),
                geometry_units='meters', abort_event=abort, execution_options=dict(ram_budget_gib=1))
    assert angle_batch.limit() == 256 and current_options() is None


@pytest.mark.parametrize('busy', [False, True])
def test_recovery_releases_only_idle_workers_and_reprices_live_budget(busy):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from ghost_backend.execution.options import execution_scope
    pool = SimpleNamespace(busy=busy, closed=False, reserved_bytes=123, close=Mock())
    resources = {'compressed_tile_workers': pool}
    def price():
        return 2. if resources else .5
    with angle_batch.scope(), execution_scope(dict(factorization='compressed')), \
         patch('ghost_backend.twod.preparation.run_resources', return_value=resources):
        peak, budget = angle_batch.recover(2., 1., price, lambda: 1., lambda: None, 361)
        assert angle_batch.events()[0]['admitted'] == (not busy)
        assert (peak <= budget) == (not busy)
        assert configured_batch_size() == (1 if busy else 256)
    assert pool.close.call_count == (0 if busy else 1)


def test_fixed_worker_plan_carries_smaller_batch_and_defers_wrong_backend_fit():
    options = validate_options(dict(factorization='compressed', angle_batch_size=256))
    choice = dict(selected='compressed', retry_order=[], angle_batch_size=64,
        candidates=dict(compressed=dict(peak_gb=.7, cost=10.), dense=dict(peak_gb=4., cost=5.)))
    with patch('ghost_backend.execution.selection.select_backend', return_value=choice):
        records = frequency_sweep._plan({}, options, False, [1.], 1, 1., 2)
    assert records[0]['angle_batch_size'] == 64
    assert records[0]['selection'] is None
    choice['selected'] = 'dense'
    choice['candidates']['compressed']['peak_gb'] = 2.
    choice['candidates']['dense']['peak_gb'] = .5
    with patch('ghost_backend.execution.selection.select_backend', return_value=choice):
        assert frequency_sweep._plan({}, options, False, [1.], 1, 1., 2) == []


def worker_probe(batch):
    """Run the real frequency worker in a fresh Python interpreter."""
    frequency_sweep._STOP, frequency_sweep._PROGRESS = threading.Event(), queue.Queue()
    payload = dict(solver='solve_monostatic_rcs_2d', frequency=1., frequencies=[1.],
        arguments=dict(geometry_snapshot=fixture('rectangle', 24), elevations_deg=list(range(361)),
                       geometry_units='meters'),
        options=validate_options(dict(factorization='compressed', ram_budget_gib=4,
                                      assembly_threads=2, blas_threads=2)),
        cpus=2, memory_gib=1., precision='double', selection=None, directory=None,
        angle_batch_size=batch)
    with patch.object(solver, '_estimate_memory_gb', side_effect=forecast), \
         patch.object(solver, '_detect_available_gb', return_value=8.):
        result = frequency_sweep._compute(payload)['result']
    meta = result['metadata']
    return dict(mode=meta['execution_options']['factorization'],
        batch=meta['execution_options']['angle_batch_size'], reservation=meta['frequency_worker']['memory_reservation_gib'],
        recovery=meta.get('angle_batch_recovery', []),
        counts={pol:len(result['co_solved_samples'][pol]) for pol in ('VV', 'HH')})


@pytest.mark.parametrize('batch', [64, 256])
def test_fresh_worker_respects_forecast_batch_and_its_own_reservation(batch):
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(root.parent), str(root/'tests'))),
               OPENBLAS_NUM_THREADS='2', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
    code = 'import json; from test_compressed_recovery import worker_probe; print(json.dumps(worker_probe({})))'.format(batch)
    process = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=60)
    assert process.returncode == 0, process.stdout + process.stderr
    result = json.loads(process.stdout)
    assert result['mode'] == 'compressed' and result['batch'] == 64
    assert result['reservation'] == 1. and result['counts'] == dict(VV=361, HH=361)
    assert bool(result['recovery']) == (batch == 256)
    if result['recovery']:
        assert all(a['budget_gib'] == 1. for a in result['recovery'][0]['attempts'])
