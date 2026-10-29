"""Product team lifetime, bounded reductions, retained arrays and sample coverage."""
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from unittest import mock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.compressed import hmatrix as H
from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
from ghost_backend.execution import options
from test_hmatrix_resource_bounds import Kernel, coordinates


def make(n=512, **kwargs):
    return H.HMatrixOperator(Kernel(n), coordinates(n), leaf=32, **kwargs)


def numeric_bytes(operator):
    """Count distinct retained NumPy backing buffers, excluding the oracle."""
    seen, arrays = set(), {}
    def visit(value):
        if id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, np.ndarray):
            while isinstance(value.base, np.ndarray):
                value = value.base
            arrays[id(value)] = value.nbytes
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif type(value).__module__ == H.__name__:
            names = vars(value) if hasattr(value, '__dict__') else value.__slots__
            for name in names:
                if name not in ('oracle', 'checkpoint'):
                    visit(getattr(value, name))
    visit(operator)
    return sum(arrays.values())


@pytest.fixture
def team():
    with options.execution_scope(dict(assembly_threads=2, blas_threads=1), assembly_threads=2):
        yield


def test_factorization_reuses_one_team_and_joins_on_scope_exit(team):
    operator = make(1024)
    pools = []
    def pool(*args, **kwargs):
        result = ThreadPoolExecutor(*args, **kwargs)
        pools.append(result)
        return result
    with mock.patch.object(H, 'ThreadPoolExecutor', side_effect=pool):
        factor = HMatrixSystem(operator, operator.coordinates, 1e-8, 64*1024**2, lambda: None)
    assert factor.range_blocks > 2
    assert len(pools) == 1
    assert pools[0]._threads and all(not thread.is_alive() for thread in pools[0]._threads)
    assert H._PRODUCT_EXECUTOR.get() is None


def test_nested_scopes_reuse_only_their_operator_and_restore_on_exception(team):
    first, second = make(32, assemble=False), make(32, assemble=False)
    with first.product_scope() as outer:
        assert first._map(lambda x: x+1, [1, 2]) == [2, 3]
        with first.product_scope() as nested:
            assert nested is outer
        with pytest.raises(ValueError, match='test'):
            with second.product_scope() as inner:
                assert inner is not outer
                second._map(lambda x: x, [1, 2])
                inner_pool = inner.pool
                raise ValueError('test')
        assert H._PRODUCT_EXECUTOR.get() is outer
        assert all(not thread.is_alive() for thread in inner_pool._threads)
        assert first._map(lambda x: x*2, [1, 2]) == [2, 4]
    assert H._PRODUCT_EXECUTOR.get() is None


def test_failed_product_joins_running_jobs_before_reuse(team):
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    operator = make(32, assemble=False)
    def function(index):
        if index == 0:
            assert started.wait(5.)
            release.set()
            raise ValueError('bad product')
        if index == 1:
            started.set()
            assert release.wait(5.)
            finished.set()
        return index
    with operator.product_scope():
        with pytest.raises(ValueError, match='bad product'):
            operator._map(function, list(range(20)))
        assert finished.is_set()
        assert operator._map(lambda x: x+2, [1, 2]) == [3, 4]


def test_cancellation_joins_and_clears_product_scope(team):
    entered, abort = threading.Event(), threading.Event()
    finished = []
    def check():
        if abort.is_set():
            raise InterruptedError('canceled')
    operator = make(32, assemble=False, checkpoint=check)
    def function(index):
        entered.set()
        try:
            assert abort.wait(5.)
            check()
        finally:
            finished.append(index)
    def cancel():
        assert entered.wait(5.)
        abort.set()
    trigger = threading.Thread(target=cancel)
    trigger.start()
    try:
        with pytest.raises(InterruptedError, match='canceled'):
            operator._map(function, [0, 1, 2, 3])
    finally:
        abort.set()
        trigger.join(5.)
    assert finished
    assert H._PRODUCT_EXECUTOR.get() is None


def test_parallel_callers_do_not_share_product_owners():
    operator = make(32, assemble=False)
    def caller(_):
        with options.execution_scope(dict(assembly_threads=2, blas_threads=1), assembly_threads=2):
            with operator.product_scope() as owner:
                assert operator._map(lambda x: x+1, [1, 2]) == [2, 3]
                return owner
    with ThreadPoolExecutor(max_workers=2) as callers:
        first, second = list(callers.map(caller, range(2)))
    assert first is not second
    assert first.pool is second.pool is None


def test_nested_cpu_allocation_does_not_widen_a_live_team(team):
    operator = make(32, assemble=False)
    parent_thread = threading.get_ident()
    with operator.product_scope():
        with options.cpu_allocation_scope(1):
            assert operator._map(lambda _: threading.get_ident(), [1, 2]) == [parent_thread]*2


def test_inline_products_check_cancellation_between_functions(team):
    abort, visited = [], []
    def check():
        if abort:
            raise InterruptedError('stop inline')
    operator = make(32, assemble=False, checkpoint=check)
    def visit(item):
        visited.append(item)
        abort.append(True)
    with options.cpu_allocation_scope(1):
        with pytest.raises(InterruptedError, match='stop inline'):
            operator._map(visit, [0, 1, 2])
    assert visited == [0]


@pytest.mark.parametrize('n', [256, 1024])
def test_ledger_covers_all_persistent_numeric_buffers_and_rebuild(team, n):
    operator = make(n)
    assert operator.bytes == operator.ledger.bytes == numeric_bytes(operator)
    before = operator.bytes
    operator.rebuild(operator.tolerance/10)
    assert operator.bytes == operator.ledger.bytes == numeric_bytes(operator)
    with pytest.raises(MemoryError, match='retained-storage cap'):
        make(n, budget=before-1)


def test_paired_ledger_preserves_partner_during_single_operator_rebuild(team):
    class Paired:
        oracles = [Kernel(512), Kernel(512)]
        def get_with_error(self, rows, cols):
            return [source.get_with_error(rows, cols) for source in self.oracles]
    pair = H.build_pair(Paired(), coordinates(512), leaf=32, budget=32*1024**2)
    first, partner = pair
    partner_bytes = partner.bytes
    assert first.ledger is partner.ledger
    assert first.ledger.bytes == sum(operator.bytes for operator in pair)
    # Only the row-id array is shared and conservatively charged twice.
    assert first.ledger.bytes-numeric_bytes(pair) == first.sample_rows.nbytes
    first.rebuild(first.tolerance/10)
    assert partner.bytes == partner_bytes
    assert first.ledger.bytes == sum(operator.bytes for operator in pair) == numeric_bytes(pair)


def test_sample_storage_cap_reports_partial_leaf_coverage(team):
    with mock.patch.object(H, 'SAMPLE_BYTES', 16*512*4):
        operator = make()
    assert operator.sample_values.nbytes == 16*512*4
    evidence = operator.evidence
    assert evidence['sample_leaf_count'] == 16
    assert evidence['sampled_leaf_count'] == 4
    assert evidence['sampled_leaf_fraction'] == .25
    assert evidence['sample_coverage_limited'] is True
    assert evidence['sample_row_storage_bytes'] == evidence['sample_row_storage_limit_bytes']
    assert numeric_bytes(operator) == operator.bytes


def test_default_sample_coverage_records_every_leaf(team):
    operator = make()
    assert operator.evidence['sampled_leaf_count'] == operator.evidence['sample_leaf_count']
    assert operator.evidence['sampled_leaf_fraction'] == 1.
    assert operator.evidence['sample_coverage_limited'] is False


@pytest.mark.parametrize('trans', [1, 2])
@pytest.mark.parametrize('workers', [1, 2, 8])
def test_adjoint_batches_preserve_exact_order_and_release_previous_wave(team, trans, workers):
    operator = make(1024)
    rng = np.random.default_rng(9)
    x = rng.standard_normal((operator.n, 7))+1j*rng.standard_normal((operator.n, 7))
    reference = np.zeros_like(x)
    adj = lambda value: value.T if trans == 1 else value.conj().T
    rows = sorted(operator.near+operator.far+operator.dense_far, key=lambda row: (row.kind, row.row))
    for row in rows:
        y = x[row.start:row.stop]
        value = adj(row.u)@y if row.v is None else adj(row.v)@(adj(row.u)@y)
        for (a,b), offset in zip(row.ranges, row.offsets):
            reference[a:b] += value[offset:offset+b-a]
    mapped, references, waves = operator._map, [], []
    largest = max(16*len(row.columns)*x.shape[1] for row in rows)
    def observe(function, items):
        assert all(ref() is None for ref in references)
        # Observe an eight-worker window without launching eight numerical
        # threads; scheduling cannot change its admitted result sizes.
        result = ([function(item) for item in items] if workers > 2 else mapped(function, items))
        arrays = [array for batch in result for array in batch]
        waves.append(sum(array.nbytes for array in arrays))
        references[:] = [weakref.ref(array) for array in arrays]
        return result
    allowance = 64*1024
    with mock.patch.object(H, 'ADJOINT_BATCH_BYTES', allowance), \
            mock.patch('ghost_backend.compressed.operator._thread_budget', return_value=workers), \
            mock.patch.object(operator, '_map', side_effect=observe):
        result = operator.matmul_positions(x, trans)
    np.testing.assert_array_equal(result, reference)
    assert len(waves) > 2
    assert max(waves) <= workers*max(allowance//workers, largest)
    assert all(ref() is None for ref in references)
