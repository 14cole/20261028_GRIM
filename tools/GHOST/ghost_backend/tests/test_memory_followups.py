"""Adversarial overlap, incremental allocation and phase workspace regressions."""
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import patch

import pytest
from ghost_backend.execution import memory_budget as mb
from ghost_backend.execution.options import execution_scope, memory_allocation_scope
from ghost_backend.compressed import runtime, memory
from ghost_backend.twod import solver
from test_request_memory_budget import simulated, Owned, GIB


def test_duplicate_process_credit_cannot_expand_cohort_capacity():
    with simulated(cap=12.) as (live, first):
        assert first.stable() == 12.
        a = Owned(10); first.register(a)
        with mb._STATE.override(None), simulated(cap=12.) as (_, second):
            assert second.stable() == pytest.approx(9.6)
            b = Owned(9); second.register(b)
            # Both registered payloads fit a single observed 10 GiB increase.
            with patch.object(mb, 'process_memory', return_value=(10*GIB, 10*GIB)), \
                 patch.object(solver, '_detect_available_gb', return_value=14.):
                assert first.owned()[1:] == second.owned()[1:] == (0., 0.)
                samples = (len(first.worker_samples), len(second.worker_samples))
                with mb._STATE.override(None), mb.scope() as third:
                    assert third.stable() == pytest.approx(0.)
                    assert sum(x.ceiling for x in (first, second, third)) == pytest.approx(21.6)
                assert samples == (len(first.worker_samples), len(second.worker_samples))
        assert first.shared_process  # Do not reclaim ambiguous historical growth.


def test_threaded_reservations_and_cancellation_release_capacity():
    barrier = threading.Barrier(4)
    reservations = {}
    def reserve(index):
        with execution_scope(dict(ram_budget_gib=12.)), mb.scope() as state:
            barrier.wait(timeout=10)
            value = state.stable()
            reservations[index] = value
            barrier.wait(timeout=10)
            assert state.shared_process
            if index == 0:
                raise InterruptedError('cancelled request')
            return value
    with patch.object(solver, '_detect_available_gb', return_value=24.), \
         patch('ghost_backend.execution.memory.windows_available_commit_bytes', return_value=None):
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(reserve, i) for i in range(4)]
            values = []
            for future in futures:
                try: values.append(future.result(timeout=15))
                except InterruptedError: pass
        assert sum(values) <= 21.6+1e-9
        assert sum(reservations.values()) == pytest.approx(21.6)
        assert not list(mb._REQUESTS)
        with execution_scope(dict(ram_budget_gib=24.)), mb.scope() as fresh:
            assert fresh.stable() == pytest.approx(21.6)
            assert not fresh.shared_process


def test_reservation_never_samples_another_requests_workers():
    class Workers:
        def memory_snapshot(self):
            raise AssertionError('peer sampled during admission')
    with simulated(cap=8.) as (_, first):
        first.stable()
        worker = Workers(); first.register(worker, 'workers')
        with mb._STATE.override(None), simulated(cap=24.) as (_, second):
            assert second.stable() == pytest.approx(13.6)


def test_unpriced_request_is_marked_shared_before_allocations():
    with simulated(cap=8.) as (_, first):
        assert first.ceiling is None
        with mb._STATE.override(None), simulated(cap=8.) as (_, second):
            assert first.shared_process and second.shared_process


def test_public_options_can_be_applied_after_scope_entry():
    with simulated() as (_, ledger):
        with execution_scope(dict(ram_budget_gib=6.)):
            assert ledger.stable() == 6.
        assert ledger.stable() == 6.


def test_reload_does_not_charge_existing_gui_baseline_again():
    with simulated(available=20.) as (live, ledger):
        ledger.baseline_rss = ledger.baseline_private = 4*GIB
        assert ledger.stable() == 18.
        value = Owned(4); ledger.register(value)
        live.update(available=6., rss=8*GIB, private=8*GIB)
        mb.admit_reload(2*GIB, workspace=0)
        assert ledger.events[-1]['admitted']
        assert ledger.events[-1]['additional_allocation_gib'] == 2.


def test_reload_does_not_compare_private_commit_to_physical_headroom():
    with simulated(available=20., commit=100*GIB) as (live, ledger):
        ledger.baseline_rss = GIB; ledger.baseline_private = 10*GIB
        ledger.stable()
        live.update(available=8., rss=GIB, private=10*GIB)
        mb.admit_reload(GIB, workspace=0)
        assert ledger.events[-1]['admitted']


@pytest.mark.parametrize('binding', ['live_physical_ram', 'live_commit_headroom', 'stable_reservation'])
def test_reload_still_enforces_each_independent_constraint(binding):
    with simulated(available=20., cap=6., commit=20*GIB) as (live, ledger):
        ledger.stable()
        value = Owned(4); ledger.register(value)
        live.update(rss=4*GIB, private=4*GIB)
        if binding == 'live_physical_ram': live['available'] = 3.
        if binding == 'live_commit_headroom': live['commit'] = 3*GIB
        with pytest.raises(MemoryError, match=binding):
            mb.admit_reload(3*GIB, workspace=0)


def test_phase_credits_only_the_matching_resident_baseline():
    with simulated(available=20., commit=20*GIB) as (live, ledger):
        ledger.baseline_rss = ledger.baseline_private = GIB//2
        ledger.stable()
        value = Owned(4); ledger.register(value)
        live.update(available=6., commit=6*GIB, rss=int(4.5*GIB), private=int(4.5*GIB))
        mb.record_plan(dict(process_baseline_bytes=GIB//2, process_geometry_bytes=2*GIB,
            phase_bytes=dict(solve=8.3*GIB)))
        mb.admit_phase('solve')
        assert ledger.last['credited_resident_gib'] == 4.5
        ledger.plan['phase_bytes']['solve'] = 8.6*GIB
        with pytest.raises(MemoryError): mb.admit_phase('solve')


def test_phase_prices_measured_payload_above_the_original_forecast():
    with simulated(available=20., cap=10.) as (live, ledger):
        ledger.stable()
        value = Owned(8); ledger.register(value)
        live.update(rss=8*GIB, private=8*GIB)
        mb.record_plan(dict(phase_bytes=dict(solve=9*GIB), nonstorage_phase_bytes=dict(solve=3*GIB)))
        with pytest.raises(MemoryError, match='11.000'): mb.admit_phase('solve')


@pytest.mark.parametrize('workspace,expected', [(2,8), (6,4), (10,0), (12,0)])
def test_workspace_allowance_has_no_sixty_percent_floor(workspace, expected):
    with simulated(cap=10.) as (_, ledger):
        mb.record_plan(dict(nonstorage_phase_bytes=dict(
            assembly=workspace*GIB, factorization=GIB, solve=GIB)))
        assert runtime.storage_budget() == expected*GIB
        with memory_allocation_scope(8.):
            assert runtime.storage_budget() <= 8*GIB


def test_speculative_mesh_forecast_does_not_change_active_allowance():
    with simulated(cap=10.) as (_, ledger):
        original = dict(nonstorage_phase_bytes=dict(assembly=2*GIB, factorization=GIB, solve=GIB))
        mb.record_plan(original)
        before = runtime.storage_budget()
        solver._estimate_memory_gb(100, False, system_dofs=100, dense_resources={})
        assert ledger.plan is original and runtime.storage_budget() == before
        resources = {}
        solver._estimate_memory_gb(100, False, system_dofs=100, dense_resources=resources,
            activate_memory_plan=True)
        assert ledger.plan is resources['memory_estimate']
        assert runtime.storage_budget() == ledger.plan['storage_limit_bytes']


def test_hierarchical_workspace_remains_valid_when_cap_enables_pairing():
    model = dict(operator_bytes=GIB, inverse_bytes=GIB, inverse_peak_bytes=2*GIB,
        assembly_workspace_bytes=GIB, method='test', coefficients=1, inverse_rank=1)
    with patch('ghost_backend.compressed.hmatrix.selected', return_value=True):
        small = memory.forecast(100, 200, 1, 1, 1, 2*GIB, {'hmatrix_storage': model})
        large = memory.forecast(100, 200, 1, 1, 1, 8*GIB, {'hmatrix_storage': model})
    assert small['resident_operator_bytes'] == GIB
    assert large['resident_operator_bytes'] == 2*GIB
    assert small['nonstorage_phase_bytes'] == large['nonstorage_phase_bytes']
    assert large['nonstorage_phase_bytes']['assembly'] >= 2*GIB


def test_explicit_payload_cap_remains_explicit():
    with simulated(cap=10.) as (_, ledger), execution_scope(dict(
            factorization='compressed', compressed_storage_mib=1024, ram_budget_gib=10.)):
        resources = {}
        solver._estimate_memory_gb(100, False, system_dofs=100, dense_resources=resources,
            activate_memory_plan=True)
        assert runtime.storage_budget() == GIB
        assert ledger.plan['storage_policy'] == 'explicit_payload_cap'


def test_analytic_zero_system_clears_previous_mesh_phase_plan():
    with simulated(cap=10.) as (_, ledger):
        mb.record_plan(dict(process_baseline_bytes=GIB, phase_bytes=dict(solve=8*GIB)))
        solver._estimate_memory_gb(100, False, dense_resources=dict(analytic_zero=True),
            activate_memory_plan=True)
        assert ledger.plan is None


def test_refusal_identifies_initial_commit_cap_with_free_physical_ram():
    with simulated(available=20., commit=10*GIB) as (_, ledger):
        with pytest.raises(MemoryError, match='initial_commit_headroom'):
            ledger.require(9.5, 'large factor')
        assert ledger.last['available_gib'] == 20.
        assert ledger.last['reservation_binding_constraint'] == 'initial_commit_headroom'


def test_refusal_identifies_tighter_nested_scheduler_cap():
    with simulated(available=20.) as (_, ledger):
        assert ledger.stable() == 18.
        with memory_allocation_scope(6.):
            with pytest.raises(MemoryError, match='scheduler_reservation'):
                ledger.require(7., 'nested factor')


def test_reload_total_includes_measured_owned_workers():
    class Workers:
        def memory_snapshot(self):
            return dict(complete=True, unique_resident_bytes=6*GIB, private_bytes=7*GIB)
    with simulated(available=24., cap=8.) as (_, ledger):
        worker = Workers(); ledger.register(worker, 'workers')
        with pytest.raises(MemoryError, match='stable_reservation'):
            mb.admit_reload(3*GIB, workspace=0)


def test_two_real_public_solves_overlap_without_reservation_or_field_changes():
    import numpy as np
    from test_experimental_cpu import fixture
    available = solver._detect_available_gb()
    if available is None or available < 5.:
        pytest.skip('Two bounded real solves need 5 GiB available for this integration test')
    options = dict(factorization='compressed', compressed_storage_mib=0,
        assembly_threads=1, blas_threads=1, ram_budget_gib=2.)
    def solve():
        return solver.solve_monostatic_rcs_2d_certified(fixture('pec',48), [.6], [0.,90.],
            geometry_units='meters', execution_options=options)
    reference = solve()
    barrier = threading.Barrier(2)
    local = threading.local()
    original = mb.MemoryBudget.enrol
    def enrol(state):
        original(state)
        if not getattr(local, 'joined', False):
            local.joined = True
            barrier.wait(timeout=15)
    # Requests overlap at entry. The existing BLAS lock may serialize their
    # numerical phases; waiting for both inside that lock would deadlock.
    with patch.object(mb.MemoryBudget, 'enrol', new=enrol), \
         ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(solve) for _ in range(2)]
        results = [future.result(timeout=30) for future in futures]
    accounts = [result['metadata']['memory_accounting'] for result in results]
    assert all(account['shared_process'] for account in accounts)
    assert sum(account['last_check']['stable_reservation_gib'] for account in accounts) <= min(
        account['cohort_capacity_gib'] for account in accounts)
    for result in results:
        assert result['metadata']['quality_gate']['passed']
        assert result['metadata']['mesh_convergence_certified']
        for pol in ('VV','HH'):
            actual = [[r['rcs_amp_real'], r['rcs_amp_imag']] for r in result['co_solved_samples'][pol]]
            expected = [[r['rcs_amp_real'], r['rcs_amp_imag']] for r in reference['co_solved_samples'][pol]]
            np.testing.assert_array_equal(actual, expected)
