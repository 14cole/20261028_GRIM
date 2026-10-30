"""Cheap live worker charges must never become whole-footprint residency credit."""
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from ghost_backend.execution import memory_budget as mb
from ghost_backend.compressed.worker_pool import WorkerPool
from test_request_memory_budget import simulated, Owned


def pool():
    worker = WorkerPool.__new__(WorkerPool)
    worker.closed, worker.busy = False, False
    worker.workers, worker.payload_bytes, worker.generation = 1, 0, 1
    worker.executor = SimpleNamespace(_processes={1: SimpleNamespace(pid=123)})
    return worker


def test_incremental_uses_live_charge_and_full_admission_keeps_unique_credit():
    worker = pool()
    cheap = SimpleNamespace(rss=2*mb.GIB, private=3*mb.GIB)
    full = SimpleNamespace(rss=2*mb.GIB, private=3*mb.GIB, uss=mb.GIB)
    with simulated(available=8, cap=6) as (live, ledger), patch('psutil.Process') as process:
        process.return_value.memory_info.return_value = cheap
        process.return_value.memory_full_info.return_value = full
        mb.register(worker, 'workers')
        assert ledger.owned(incremental=True) == (0, 0, 0)
        assert ledger.worker_ownership == (2, 3)
        assert process.return_value.memory_full_info.call_count == 0
        # Large construction checks always refresh, including live OS pressure.
        with mb.construction_allocation(32*1024**2, 'Compressed inverse test'): pass
        with mb.construction_allocation(32*1024**2, 'Compressed inverse test'): pass
        assert process.return_value.memory_info.call_count == 3
        live['available'] = .1
        with pytest.raises(MemoryError, match='live_physical_ram'):
            with mb.construction_allocation(32*1024**2, 'Compressed inverse test'): pass
        assert ledger.pending_construction_bytes == 0
        assert ledger.owned() == (0, 1, 3)
        assert process.return_value.memory_full_info.call_count == 1


def test_platform_without_private_commit_uses_full_probe_without_rss_credit():
    with patch('psutil.Process') as process:
        process.return_value.memory_info.return_value = SimpleNamespace(rss=100)
        process.return_value.memory_full_info.return_value = SimpleNamespace(rss=100, uss=60)
        sample = pool().incremental_memory_snapshot()
        assert sample['complete'] and sample['rss_bytes'] == 100
        assert sample['unique_resident_bytes'] == 0
        assert process.return_value.memory_full_info.call_count == 1


def test_failed_worker_read_gives_no_credit_and_disables_observation_reuse():
    worker = pool()
    with simulated(available=8, cap=6) as (_, ledger), patch('psutil.Process', side_effect=OSError('gone')):
        mb.register(worker, 'workers')
        with mb.construction_allocation(1024, 'Compressed inverse test'): pass
        assert ledger.construction_lease is None
        assert ledger.worker_ownership == (0, 0)
        assert not ledger.worker_samples[-1]['complete']


@pytest.mark.parametrize('unique,accepted', [(.5, True), (2.5, False)])
def test_shared_rss_bound_is_refined_once_before_reservation_refusal(unique, accepted):
    worker = pool()
    cheap = SimpleNamespace(rss=3*mb.GIB, private=mb.GIB)
    full = SimpleNamespace(rss=3*mb.GIB, private=mb.GIB, uss=int(unique*mb.GIB))
    with simulated(available=8, cap=2) as (_, ledger), patch('psutil.Process') as process:
        process.return_value.memory_info.return_value = cheap
        process.return_value.memory_full_info.return_value = full
        mb.register(worker, 'workers')
        if accepted:
            mb.admit_reload(32*1024**2, workspace=0)
        else:
            with pytest.raises(MemoryError, match='stable_reservation'):
                mb.admit_reload(32*1024**2, workspace=0)
        assert process.return_value.memory_info.call_count == 1
        assert process.return_value.memory_full_info.call_count == 1
        assert ledger.last['worker_charge_refined']
        assert ledger.check_count == 1


@pytest.mark.parametrize('private,overhead,unique,accepted', [
    (1.5, 0, .1, True), (.2, 1.5, .1, True), (1.5, 0, 1, False)])
def test_parent_rss_dominance_does_not_skip_detailed_refusal_recheck(private, overhead, unique, accepted):
    worker = pool()
    cheap = SimpleNamespace(rss=mb.GIB, private=int(private*mb.GIB))
    full = SimpleNamespace(rss=mb.GIB, private=int(private*mb.GIB), uss=int(unique*mb.GIB))
    with simulated(available=8, cap=3.5) as (live, ledger), patch('psutil.Process') as process:
        process.return_value.memory_info.return_value = cheap
        process.return_value.memory_full_info.return_value = full
        payload = Owned(.5)
        mb.register(worker, 'workers')
        mb.register(payload)
        ledger.plan = dict(process_geometry_bytes=int(overhead*mb.GIB))
        live.update(rss=3*mb.GIB, private=mb.GIB)
        if accepted:
            mb.admit_reload(int(.2*mb.GIB), workspace=0)
            assert ledger.last['limit_gib'] == pytest.approx(.4)
        else:
            with pytest.raises(MemoryError, match='stable_reservation'):
                mb.admit_reload(int(.2*mb.GIB), workspace=0)
        assert process.return_value.memory_info.call_count == 1
        assert process.return_value.memory_full_info.call_count == 1
        assert ledger.last['worker_charge_refined']
        assert ledger.check_count == 1


def test_worker_sample_report_explains_unmeasured_unique_memory():
    with simulated() as (_, ledger):
        report = mb.report()
        assert 'not measured for credit' in report['worker_samples_note']
        assert 'residency_credit_eligible=true' in report['worker_samples_note']
