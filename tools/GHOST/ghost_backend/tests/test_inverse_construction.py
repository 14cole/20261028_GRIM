"""Reject before construction allocation; release ownership and preserve solves."""
import gc
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest
from ghost_backend.compressed import construction, inverse, preconditioner_hints as hints
from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
from ghost_backend.execution import memory_budget as mb, options
from ghost_backend.linalg import hierarchical as hf
from test_request_memory_budget import simulated, Owned
from test_hmatrix_product_resources import make


class Owner:
    bytes = 0
    checkpoint = staticmethod(lambda: None)


def test_pending_allocations_get_no_residency_credit_and_release_on_cancel():
    with simulated(available=4, cap=1) as (live, ledger):
        with pytest.raises(InterruptedError):
            with mb.construction_allocation(700*1024**2, 'test', reload_allowance=600*1024**2):
                assert ledger.owned() == (0., 0., 0.)
                checks = ledger.check_count
                mb.admit_reload(600*1024**2, workspace=0)
                assert ledger.check_count == checks
                with pytest.raises(MemoryError):
                    with mb.construction_allocation(400*1024**2, 'nested'):
                        pytest.fail('oversubscribed reservation')
                raise InterruptedError()
        assert ledger.pending_construction_bytes == 0
        with mb.construction_allocation(900*1024**2, 'retry'):
            pass


def test_peer_cannot_spend_pending_physical_headroom():
    ready, done = threading.Event(), threading.Event()
    with simulated(available=4, cap=1) as (live, first):
        def peer():
            with options.execution_scope(dict(ram_budget_gib=1)), mb.scope() as second:
                ready.set()
                assert done.wait(10)
                with pytest.raises(MemoryError, match='live_physical_ram'):
                    with mb.construction_allocation(400*1024**2, 'peer'):
                        pytest.fail('peer overspent pending headroom')
                assert second.pending_construction_bytes == 0
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(peer)
            assert ready.wait(10)
            with mb.construction_allocation(700*1024**2, 'first'):
                live['available'] = 1.3  # 0.9 GiB after the initial reserve.
                done.set()
                future.result(timeout=10)
        assert first.pending_construction_bytes == 0


def test_tracked_build_and_temporary_views_count_once_and_cleanup():
    owner = Owner()
    owner.bytes = 100
    guard = construction.Construction(owner)
    array = np.zeros((20, 30), complex)
    with simulated(available=4) as (_, ledger):
        with pytest.raises(RuntimeError):
            with guard.track():
                with guard.step('temporary', 256, array, array[:, :2]):
                    assert ledger.owned()[0]*mb.GIB == owner.bytes+array.nbytes
                    raise RuntimeError('construction failure')
        assert ledger.owned() == (0., 0., 0.)
        assert ledger.pending_construction_bytes == 0


@pytest.mark.parametrize('stage', ['sample products', 'range extension', 'projected QR', 'projected SVD'])
def test_sampled_allocation_rejected_before_operation_and_releases(stage):
    rng = np.random.default_rng(14)
    matrix = rng.normal(size=(90, 3)) @ rng.normal(size=(3, 80))
    block = hf.Block(matrix, np.arange(90), np.arange(80), lambda: None)
    owner = Owner()
    guard = construction.Construction(owner)
    block.construction = guard
    with simulated(available=4) as (_, ledger):
        original = ledger.require_reload
        labels = []
        operation = (block, 'matmul') if stage == 'sample products' else (
            hf.la, 'svd' if stage == 'projected SVD' else 'qr')
        counts = []
        def check(count, context='reload'):
            labels.append(context)
            if context.endswith(stage):
                counts.append(spy.call_count)
                raise MemoryError(stage)
            return original(count, context)
        with guard.track(), mock.patch.object(ledger, 'require_construction', side_effect=lambda count, context: (check(count,context) or dict(live_check=True,process_sample=None))), \
                mock.patch.object(*operation, wraps=getattr(*operation)) as spy:
            with pytest.raises(MemoryError, match=stage):
                hf.compress_sampled(block, 1e-9, 32, rng)
            assert counts == [spy.call_count]
        assert labels[-1].endswith(stage)
        assert ledger.pending_construction_bytes == 0
        assert ledger.owned() == (0., 0., 0.)


@pytest.mark.parametrize('stage', ['leaf coefficients', 'leaf or correction LU', 'Woodbury correction'])
def test_tree_refusal_releases_partial_build_before_retry(stage):
    op = make(128)
    references = []
    original_track = construction.Construction.track
    @contextmanager
    def observed_track(guard):
        references.append(weakref.ref(guard.owner))
        with original_track(guard):
            yield guard
    with simulated(available=4) as (_, ledger):
        original = ledger.require_reload
        def check(count, context='reload'):
            if context.endswith(stage):
                raise MemoryError(stage)
            return original(count, context)
        # Catch in a helper so pytest's ExceptionInfo cannot retain the tree.
        def rejected():
            try:
                HMatrixSystem(op, op.coordinates, 1e-8, 64*1024**2, lambda: None)
            except MemoryError:
                return
            pytest.fail('missing refusal')
        with mock.patch.object(ledger, 'require_construction', side_effect=lambda count, context: (check(count,context) or dict(live_check=True,process_sample=None))), \
                mock.patch.object(construction.Construction, 'track', observed_track):
            rejected()
        gc.collect()
        assert references and all(ref() is None for ref in references)
        assert ledger.pending_construction_bytes == 0
        assert ledger.owned() == (0., 0., 0.)
        factor = HMatrixSystem(op, op.coordinates, 1e-8, 64*1024**2, lambda: None)
        b = np.ones((op.n, 2), complex)
        assert np.linalg.norm(op.matmul(factor.apply(b, solve=True))-b)/np.linalg.norm(b) < 1e-6


def test_leaf_retained_cap_checked_before_coefficient_allocation():
    oracle = inverse.Oracle(np.eye(16, dtype=complex))
    with mock.patch.object(oracle, 'get', side_effect=AssertionError('coefficient allocation')):
        with pytest.raises(MemoryError, match='retained-storage'):
            inverse.CompressedSystem(oracle, np.arange(16)[:, None], budget=1024, inverse_only=True)


def test_upgrade_old_inverse_remains_owned_without_double_counting():
    with simulated(available=4) as (_, ledger):
        old = Owned(.1)
        holder = SimpleNamespace(factor=old, _construction_previous=old)
        # SimpleNamespace has no weak-reference support.
        class Factor: pass
        factor = Factor()
        factor.factor, factor._construction_previous = holder.factor, holder._construction_previous
        mb.register(factor, 'factor')
        assert ledger.owned()[0] == pytest.approx(.1)
        factor.factor = None
        assert ledger.owned()[0] == pytest.approx(.1)


def observed_factor(n, actual, forecast):
    return SimpleNamespace(a=SimpleNamespace(n=n, bytes=actual, oracle=SimpleNamespace(kind='TE'),
        evidence={'operator': 'hmatrix'}), factor=SimpleNamespace(bytes=actual, evidence={}),
        event={'factorizations': 1}, storage_forecast=dict(model='compressed_hmatrix_v2',
            operator_bytes=forecast, inverse_ceiling_bytes=forecast, inverse_construction_bytes=3*forecast))


def test_shadow_measurements_are_request_local_and_never_discount_plan():
    cpu = SimpleNamespace(current_resources={'formulation': 'single_dielectric'})
    with mock.patch('ghost_backend.execution.cpu.current_state', return_value=cpu):
        with hints.scope([2.], {'shape': 'inlet'}):
            first, second = observed_factor(100, 100, 400), observed_factor(150, 500, 800)
            hints.observe_storage(first)
            hints.observe_storage(second)
            event = second.event['memory_forecast_observation']
            assert event['previous_mesh_proposal']['operator_bytes'] == 300
            assert event['previous_mesh_proposal']['storage_underpredicted'] == [True, True]
            assert not event['forecast_discount_applied']
            assert second.storage_forecast['operator_bytes'] == 800
        with hints.scope([2.], {'shape': 'inlet'}):
            fresh = observed_factor(150, 500, 800)
            hints.observe_storage(fresh)
            assert 'previous_mesh_proposal' not in fresh.event['memory_forecast_observation']
        with hints.scope([1., 2.], {'shape': 'inlet'}):
            sweep = observed_factor(150, 500, 800)
            hints.observe_storage(sweep)
            assert 'memory_forecast_observation' not in sweep.event
