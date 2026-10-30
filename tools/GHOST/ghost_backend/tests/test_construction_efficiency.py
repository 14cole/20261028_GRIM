"""Bounded observation reuse, explicit reload coverage and diagnostic retention."""
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from ghost_backend.execution import memory_budget as mb, options
from ghost_backend.compressed import preconditioner_hints as hints
from test_request_memory_budget import simulated, Owned
from test_inverse_construction import observed_factor

MIB = 1024**2


def allocate(count=MIB):
    with mb.construction_allocation(count, 'Compressed inverse test') as observation:
        return observation['live_check']


def test_small_groups_consume_quota_without_refund_and_refresh_when_exhausted():
    with simulated(available=8, cap=4) as (_, ledger), patch.object(mb.time, 'monotonic', return_value=10.):
        assert allocate()
        quota = ledger.construction_lease['quota']
        checks = quota//MIB
        for _ in range(checks-1):
            assert not allocate()
        assert allocate()
        assert ledger.construction_checks['live'] == 2
        assert ledger.pending_construction_bytes == 0


@pytest.mark.parametrize('change', ['expiry', 'cap', 'peer', 'ownership', 'large', 'reload', 'plan'])
def test_observation_invalidations_refresh_before_next_allocation(change):
    with simulated(available=8, cap=4) as (_, ledger), patch.object(mb.time, 'monotonic', return_value=10.) as clock:
        assert allocate()
        if change == 'expiry': clock.return_value = 10.051
        elif change == 'cap': ledger.construction_lease['caps'] = {'explicit_ram_budget': 5}
        elif change == 'peer': ledger.shared_process = True
        elif change == 'ownership':
            payload = Owned(.001)
            mb.register(payload)
        elif change == 'reload': mb.admit_reload(1, workspace=0)
        elif change == 'plan': mb.record_plan({})
        assert allocate(16*MIB if change == 'large' else MIB)


def test_unmodeled_numeric_growth_forces_refresh_even_without_registration():
    with simulated(available=8, cap=4) as (_, ledger), patch.object(mb.time, 'monotonic', return_value=10.):
        payload = Owned(0)
        mb.register(payload)
        assert allocate()
        payload.bytes = 3*MIB
        assert allocate()


def test_exhausted_headroom_refreshes_and_rejects_before_allocating():
    with simulated(available=8, cap=4) as (live, ledger), patch.object(mb.time, 'monotonic', return_value=10.):
        assert allocate()
        ledger.construction_lease['remaining'] = MIB-1
        live['available'] = .1
        with pytest.raises(MemoryError): allocate()
        assert ledger.pending_construction_bytes == 0
        assert ledger.events[-1]['admitted'] is False
        assert ledger.construction_lease is None


def test_worker_owners_never_reuse_live_samples():
    class Worker:
        calls = 0
        def memory_snapshot(self):
            self.calls += 1
            return dict(complete=True, unique_resident_bytes=0, private_bytes=0)
    with simulated(available=8, cap=4) as (_, ledger):
        worker = Worker()
        mb.register(worker, 'workers')
        assert allocate() and allocate()
        assert worker.calls == 2
        assert ledger.construction_lease is None


def test_idle_worker_reuse_refreshes_on_activity_identity_and_incomplete_sample():
    class Worker:
        calls = 0
        busy = False
        generation = 0
        complete = True
        def construction_observation_key(self):
            return None if self.busy else (self.generation,)
        def memory_snapshot(self):
            self.calls += 1
            return dict(complete=self.complete, unique_resident_bytes=0, private_bytes=0)
    with simulated(available=8, cap=4) as (_, ledger), patch.object(mb.time, 'monotonic', return_value=10.):
        worker = Worker()
        mb.register(worker, 'workers')
        assert allocate() and not allocate()
        assert worker.calls == 1
        worker.generation += 1
        assert allocate() and not allocate()
        worker.busy = True
        assert allocate() and allocate()
        worker.busy = False
        assert allocate() and not allocate()
        worker.generation += 1
        worker.complete = False
        assert allocate() and allocate()
        assert ledger.construction_lease is None


def test_worker_identity_covers_payload_process_replacement_and_closure():
    from ghost_backend.compressed.worker_pool import WorkerPool
    worker = WorkerPool.__new__(WorkerPool)
    worker.busy, worker.closed = False, False
    worker.generation, worker.workers, worker.payload_bytes = 1, 2, 100
    worker.executor = SimpleNamespace(_processes={1: SimpleNamespace(pid=123)})
    previous = worker.construction_observation_key()
    for name, value in [('generation', 2), ('payload_bytes', 200), ('closed', True)]:
        setattr(worker, name, value)
        current = worker.construction_observation_key()
        assert current != previous
        previous = current
    worker.executor._processes[1].pid = 456
    assert worker.construction_observation_key() != previous
    worker.executor._processes[1].pid = None
    assert worker.construction_observation_key() is None
    worker.busy = True
    assert worker.construction_observation_key() is None


def test_reload_coverage_defaults_to_zero_and_is_consumable_when_explicit():
    with simulated(available=8, cap=4) as (_, ledger):
        with mb.construction_allocation(8*MIB, 'Compressed inverse test'):
            checks = ledger.check_count
            mb.admit_reload(MIB, workspace=0)
            assert ledger.check_count == checks+1
        with mb.construction_allocation(8*MIB, 'Compressed inverse test', reload_allowance=2*MIB):
            checks = ledger.check_count
            mb.admit_reload(MIB, workspace=0)
            mb.admit_reload(MIB, workspace=0)
            assert ledger.check_count == checks
            mb.admit_reload(MIB, workspace=0)
            assert ledger.check_count == checks+1
        with pytest.raises(ValueError):
            with mb.construction_allocation(MIB, 'bad', reload_allowance=2*MIB): pass


def test_admitted_groups_preserve_phase_events_but_refusals_are_retained():
    with simulated(available=8, cap=4) as (_, ledger):
        ledger.require(.1, 'Compressed factorization')
        for _ in range(100): allocate()
        assert len(ledger.events) == 1
        with pytest.raises(MemoryError): allocate(8*mb.GIB)
        report = mb.report()
        assert report['checks'][-1]['admitted'] is False
        assert report['checks'][0]['context'] == 'Compressed factorization'
        assert report['summarized_construction_checks'] == 100
        assert report['total_checks'] == 102
        assert report['omitted_earlier_checks'] == 0


def test_construction_comparison_is_accounted_not_a_measured_peak_or_discount():
    cpu = SimpleNamespace(current_resources={'formulation': 'single_dielectric'})
    with patch('ghost_backend.execution.cpu.current_state', return_value=cpu), hints.scope([2.], {'shape':'inlet'}):
        factor = observed_factor(100, 100, 400)
        factor.factor.evidence['construction'] = {'peak_accounted_build_bytes': 1800}
        hints.observe_storage(factor)
        comparison = factor.event['memory_forecast_observation']['construction_comparison']
        assert comparison['accounted_to_forecast_ratio'] == 1.5
        assert comparison['accounted_exceeds_forecast'] is True
        assert comparison['kind'] == 'accounted_allowance_not_measured_peak'
        assert not comparison['forecast_discount_applied']
        assert factor.storage_forecast['inverse_construction_bytes'] == 1200
