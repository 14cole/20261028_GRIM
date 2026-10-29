"""H-matrix admission, bounded result storage, and cooperative cancellation."""
import sys
import threading
import time
import weakref
from concurrent.futures import Future
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.compressed import hmatrix as H
from ghost_backend.execution import options


class ImmediatePool:
    """Deterministic submission/accounting observation without extra threads."""
    def __init__(self, max_workers, **kwargs):
        self.workers = max_workers
        self.submissions = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def submit(self, function, *args):
        self.submissions += 1
        future = Future()
        try:
            future.set_result(function(*args))
        except BaseException as exc:
            future.set_exception(exc)
        return future


class Kernel:
    def __init__(self, n, error=0.):
        self.n, self.error = n, error

    def get_with_error(self, rows, cols):
        values = 1/(1+abs(np.asarray(rows)[:, None]-np.asarray(cols)[None, :])).astype(complex)
        return values, np.full(values.shape, self.error)


def coordinates(n):
    return np.column_stack((np.arange(n, dtype=float), np.zeros(n)))


@pytest.mark.parametrize('requested,allocation,physical,expected', [
    (1, 8, 4, 1), (2, 8, 4, 2), (8, 2, 4, 2), ('auto', 8, 4, 4), ('auto', 2, 4, 2),
])
def test_runner_obeys_explicit_auto_and_scheduler_thread_caps(requested, allocation, physical, expected):
    pools, outputs = [], []
    def pool(**kwargs):
        result = ImmediatePool(**kwargs)
        pools.append(result)
        return result
    with mock.patch.object(options, '_usable_logical_cpus', return_value=8), \
            mock.patch.object(options, 'host_assembly_threads', return_value=physical), \
            options.execution_scope(dict(assembly_threads=requested, blas_threads=1), assembly_threads=allocation), \
            mock.patch.object(H, 'ThreadPoolExecutor', side_effect=pool):
        H._run([lambda check: options.allocated_cpu_budget() for _ in range(12)],
               lambda index, value: outputs.append(value), lambda: None)
    assert ([p.workers for p in pools] or [1]) == [expected]
    assert outputs == [1]*12


def test_result_window_is_bounded_and_consumption_precedes_replacement():
    pool = ImmediatePool(2)
    consumed, references = [], []
    def task(check):
        result = np.zeros(10)
        references.append(weakref.ref(result))
        return result
    def consume(index, value):
        assert pool.submissions-index <= 2
        assert sum(ref() is not None for ref in references) <= 2
        consumed.append(index)
    with options.execution_scope(dict(assembly_threads=2, blas_threads=1), assembly_threads=2), \
            mock.patch.object(H, 'ThreadPoolExecutor', return_value=pool):
        H._run([task]*20, consume, lambda: None)
    assert consumed == list(range(20))
    assert all(ref() is None for ref in references)


def test_admission_failure_stops_running_sibling_and_joins_before_returning():
    started, finished = threading.Event(), threading.Event()
    accepted = []
    def first(check):
        assert started.wait(5.)
        return 'first'
    def sibling(check):
        started.set()
        try:
            while True:
                check()
                time.sleep(.001)
        finally:
            finished.set()
    def forbidden(check):
        raise AssertionError('replacement work dispatched after admission failure')
    def reject(index, value):
        accepted.append(value)
        raise MemoryError('admission rejected')
    with options.execution_scope(dict(assembly_threads=2, blas_threads=1), assembly_threads=2):
        with pytest.raises(MemoryError, match='admission rejected'):
            H._run([first, sibling, forbidden], reject, lambda: None)
    assert accepted == ['first']
    assert finished.is_set()


def test_external_cancellation_joins_workers_without_publishing_results():
    started, finished, canceled = threading.Event(), threading.Event(), threading.Event()
    def task(check):
        started.set()
        try:
            while True:
                check()
                time.sleep(.001)
        finally:
            finished.set()
    def checkpoint():
        if canceled.is_set():
            raise InterruptedError('user canceled')
    def cancel():
        assert started.wait(5.)
        canceled.set()
    trigger = threading.Thread(target=cancel)
    trigger.start()
    try:
        with options.execution_scope(dict(assembly_threads=2, blas_threads=1), assembly_threads=2):
            with pytest.raises(InterruptedError, match='user canceled'):
                H._run([task, task], lambda *args: pytest.fail('canceled result published'), checkpoint)
    finally:
        trigger.join(timeout=5.)
    assert finished.is_set()


def test_failed_ledger_and_operator_reservations_do_not_change_accounting():
    op = H.HMatrixOperator(Kernel(32), coordinates(32), budget=100, assemble=False)
    op._reserve(80)
    with pytest.raises(MemoryError, match='retained-storage cap'):
        op._reserve(21)
    assert op.bytes == op.ledger.bytes == 80
    op._reserve(20)
    assert op.bytes == op.ledger.bytes == 100


def test_paired_far_result_is_charged_atomically():
    sources = [Kernel(512), Kernel(512)]
    class Paired:
        oracles = sources
        def get_with_error(self, rows, cols):
            return [source.get_with_error(rows, cols) for source in self.oracles]
    ledger = H._Ledger(32*1024**2)
    targets = [H.HMatrixOperator(source, coordinates(512), leaf=32, ledger=ledger, assemble=False)
               for source in sources]
    far_phase, before = [], []
    sample, reserve = H._sample, H._Ledger.reserve
    def observe_sample(*args):
        sample(*args)
        far_phase.append(True)
    def reject_first_far(self, count):
        if far_phase:
            before.append(([target.bytes for target in targets], self.bytes))
            self.budget = self.bytes + count - 1
        return reserve(self, count)
    with options.execution_scope(dict(assembly_threads=2, blas_threads=1), assembly_threads=2), \
            mock.patch.object(H, '_sample', observe_sample), \
            mock.patch.object(H._Ledger, 'reserve', reject_first_far):
        with pytest.raises(MemoryError, match='retained-storage cap'):
            H._assemble(Paired(), targets)
    assert len(before) == 1
    assert [target.bytes for target in targets] == before[0][0]
    assert ledger.bytes == before[0][1] == sum(target.bytes for target in targets)


def test_local_error_tails_accumulate_repeated_queries_for_paired_oracles():
    class Paired:
        oracles = [Kernel(100, 1e-15), Kernel(100, 2e-15)]
        def get_with_error(self, rows, cols):
            return [source.get_with_error(rows, cols) for source in self.oracles]
    fetch = H._Fetcher(Paired(), np.arange(100), lambda: None, tail_rows=[4, 8, 30])
    with mock.patch.object(H, 'QUERY_ENTRIES', 2):
        fetch([30, 4, 30], [0, 1, 2])
        fetch([8], [5, 6])
    for index, tail in enumerate(fetch.tails, 1):
        assert tail.nbytes == 3*8
        np.testing.assert_allclose(tail, np.asarray([3, 2, 6])*index*1e-15, rtol=1e-15)


@pytest.mark.parametrize('n', [512, 1024, 2048])
def test_near_tail_task_storage_is_local_and_bounded(n):
    original = H._Fetcher.__init__
    references, peaks, sizes = [], [], []
    class StopAfterNear(Exception):
        pass
    def observe(fetch, *args, **kwargs):
        original(fetch, *args, **kwargs)
        if fetch.tails is not None:
            sizes.extend(tail.size for tail in fetch.tails)
            references.extend(weakref.ref(tail) for tail in fetch.tails)
            peaks.append(sum(tail.nbytes for ref in references if (tail := ref()) is not None))
    with options.execution_scope(dict(assembly_threads=2, blas_threads=1), assembly_threads=2), \
            mock.patch.object(H, 'ThreadPoolExecutor', return_value=ImmediatePool(2)), \
            mock.patch.object(H._Fetcher, '__init__', observe), \
            mock.patch.object(H, '_sample', side_effect=StopAfterNear):
        with pytest.raises(StopAfterNear):
            H.HMatrixOperator(Kernel(n), coordinates(n), leaf=128)
    assert sizes and max(sizes) == 128
    assert max(peaks) <= 2*128*8


def test_far_results_are_admitted_before_whole_wave_completes_and_cap_stays_valid():
    ledger, completed, rejection = [], [], []
    reserve, initialize = H._Ledger.reserve, H.BlockRow.__init__
    def observed_reserve(self, count):
        ledger[:] = [self]
        try:
            return reserve(self, count)
        except MemoryError:
            rejection.append((self.bytes, self.budget, len(completed)))
            raise
    def observed_row(self, *args, **kwargs):
        initialize(self, *args, **kwargs)
        if self.kind != 0:
            completed.append(self.row)
    with options.execution_scope(dict(assembly_threads=2, blas_threads=1), assembly_threads=2), \
            mock.patch.object(H, 'ThreadPoolExecutor', return_value=ImmediatePool(2)), \
            mock.patch.object(H._Ledger, 'reserve', observed_reserve), \
            mock.patch.object(H.BlockRow, '__init__', observed_row):
        with pytest.raises(MemoryError, match='retained-storage cap'):
            H.HMatrixOperator(Kernel(1024), coordinates(1024), leaf=32, budget=4*1024**2)
    assert rejection and ledger[0].bytes <= ledger[0].budget
    # Finest far level has 32 results; the next level used to complete all
    # 16 before its first charge. One result fits the remaining cap; after
    # admitting it, only the two-worker window may finish before rejection.
    assert rejection[0][2] <= 35
