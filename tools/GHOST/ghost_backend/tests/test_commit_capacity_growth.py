"""Verified OS capacity growth, held concurrent reservations and live pressure."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import ctypes
import threading
from unittest.mock import patch

import pytest
from ghost_backend.execution import memory as native, memory_budget as mb
from ghost_backend.execution.options import execution_scope, memory_allocation_scope
from ghost_backend.compressed import runtime
from ghost_backend.twod import solver
from test_request_memory_budget import GIB, Owned


@contextmanager
def host(available=24., commit=10., limit=32., cap=None):
    live=dict(available=available,commit=commit,limit=limit,rss=0,private=0)
    def system():
        if live['limit'] is None:return None
        return dict(limit_bytes=int(live['limit']*GIB),committed_bytes=int((live['limit']-live['commit'])*GIB))
    with patch.object(solver,'_detect_available_gb',side_effect=lambda:live['available']), \
         patch.object(native,'windows_available_commit_bytes',side_effect=lambda:None if live['commit'] is None else int(live['commit']*GIB)), \
         patch.object(native,'windows_system_commit',side_effect=system), \
         patch.object(mb,'process_memory',side_effect=lambda:(live['rss'],live['private'])), \
         execution_scope(dict(ram_budget_gib=cap,compressed_storage_mib=0,factorization='compressed')):
        yield live


def test_os_backing_growth_expands_only_to_fixed_initial_physical_limit():
    with host() as live,mb.scope() as state:
        assert state.stable()==9.
        live.update(commit=20.,limit=42.)
        assert state.stable()==18.
        live.update(commit=40.,limit=62.)
        assert state.stable()==pytest.approx(21.6)
        assert len(mb.report()['commit_capacity_changes'])==2


def test_freed_commit_or_own_allocations_do_not_create_capacity():
    with host() as live,mb.scope() as state:
        assert state.stable()==9.
        live['commit']=20.
        assert state.stable()==9.
        value=Owned(8);mb.register(value)
        live.update(rss=8*GIB,private=8*GIB,available=16.,commit=12.)
        assert state.stable()==9.


def test_committed_payload_does_not_consume_new_capacity_twice():
    with host() as live,mb.scope() as state:
        assert state.stable()==9.
        value=Owned(8);mb.register(value)
        live.update(rss=8*GIB,private=8*GIB,available=16.,commit=12.,limit=42.)
        assert state.stable()==18.
        state.require(18.,'larger phase after OS expansion')
        mb.admit_reload(9*GIB,workspace=0)


def test_growth_keeps_explicit_parent_and_original_caps():
    with host(cap=12.) as live,mb.scope() as state:
        assert state.stable()==9.
        live.update(limit=62.,commit=40.)
        assert state.stable()==12.
        with memory_allocation_scope(7.):assert state.stable()==7.
        assert state.ceiling==12.
        with execution_scope(dict(ram_budget_gib=20.)):
            assert state.stable()==12.


@pytest.mark.parametrize('constraint',['physical','commit'])
def test_external_pressure_still_refuses_after_os_growth(constraint):
    with host() as live,mb.scope() as state:
        state.stable();live.update(limit=42.,commit=20.)
        assert state.stable()==18.
        if constraint=='physical':live['available']=3.
        else:live['commit']=3.
        with pytest.raises(MemoryError,match='live_'+('physical_ram' if constraint=='physical' else 'commit_headroom')):
            mb.admit_reload(2*GIB,workspace=0)


def test_growth_is_shared_once_across_overlapping_requests():
    with host(cap=12.) as live,mb.scope() as first:
        assert first.stable()==9.
        with mb._STATE.override(None),mb.scope() as second:
            assert second.stable()==0.
            live.update(limit=42.,commit=20.)
            assert first.stable()==12.
            assert second.stable()==6.
            with mb._STATE.override(None),mb.scope() as third:
                assert third.stable()==0.
                assert sum(s.ceiling for s in (first,second,third))==18.
            assert first.shared_process and first.owned()[1:]==(0.,0.)


def test_threads_cannot_each_spend_the_same_backing_limit_increase():
    barrier=threading.Barrier(4);grow=threading.Event();before={};after={}
    def request(index):
        with execution_scope(dict(ram_budget_gib=12.)),mb.scope() as state:
            before[index]=state.stable()
            barrier.wait(timeout=10);grow.wait(timeout=10)
            after[index]=state.stable()
            barrier.wait(timeout=10)
    with host() as live,ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(request,i) for i in range(3)]
        barrier.wait(timeout=10)
        assert sum(before.values())==9.
        live.update(limit=42.,commit=20.);grow.set()
        barrier.wait(timeout=10)
        assert sum(after.values())==18.
        for future in futures:future.result(timeout=10)


def test_contraction_does_not_lend_already_promised_bytes_to_a_peer():
    with host(cap=12.) as live,mb.scope() as first:
        first.stable();live.update(limit=42.,commit=20.)
        assert first.stable()==12.
        with mb._STATE.override(None),mb.scope() as second:
            assert second.stable()==6.
            live.update(limit=32.,commit=10.)
            assert first.stable()==3.
            assert second.stable()==0.
            assert first.ceiling==12. and second.ceiling==6.
            with mb._STATE.override(None),mb.scope() as third:assert third.stable()==0.
            live.update(limit=42.,commit=20.)
            assert first.stable()==12. and second.stable()==6.


@pytest.mark.parametrize('initial_limit,current_limit',[(None,42.),(32.,None)])
def test_missing_system_limit_never_authorizes_extra_capacity(initial_limit,current_limit):
    with host(limit=initial_limit) as live,mb.scope() as state:
        assert state.stable()==9.
        live.update(commit=20.,limit=current_limit)
        assert state.stable()==9.


def test_known_zero_and_unknown_physical_remain_conservative():
    for available in (0.,None):
        with host(available=available,cap=12.) as live,mb.scope() as state:
            initial=state.stable()
            live.update(commit=20.,limit=42.)
            assert state.stable()==initial


def test_automatic_payload_tracks_verified_growth_without_exceeding_workspace_remainder():
    with host() as live,mb.scope() as state:
        mb.record_plan(dict(nonstorage_phase_bytes=dict(assembly=2*GIB,factorization=GIB,solve=GIB)))
        assert runtime.storage_budget()==7*GIB
        live.update(commit=20.,limit=42.)
        assert runtime.storage_budget()==16*GIB


def test_windows_performance_probe_converts_pages_and_handles_failure():
    class Data(ctypes.Structure):
        _fields_=[('cb',ctypes.c_uint32)]+[(key,ctypes.c_size_t) for key in ('PageSize','CommitLimit','CommitTotal','CommitPeak')]
    class API:
        succeeds=True
        def GetPerformanceInfo(self,pointer,size):
            data=pointer._obj;data.PageSize=4096;data.CommitLimit=100;data.CommitTotal=40;data.CommitPeak=60
            assert size==ctypes.sizeof(Data)
            return self.succeeds
    api=API()
    with patch.object(native,'_windows_performance_api',return_value=(ctypes,Data,api)):
        assert native.windows_system_commit()==dict(limit_bytes=409600,committed_bytes=163840,peak_committed_bytes=245760)
        api.succeeds=False
        assert native.windows_system_commit() is None


def test_initial_allowance_uses_the_lower_of_process_and_system_headroom():
    with host(commit=20.),patch.object(native,'windows_system_commit',return_value=dict(
            limit_bytes=32*GIB,committed_bytes=22*GIB)),mb.scope() as state:
        assert state.initial_commit==10.
        assert state.stable()==9.


@pytest.mark.parametrize('storage', [0, 2048, 256])
def test_submission_forecast_ignores_head_host_and_live_request(storage):
    from ghost_backend.hpc.scheduler import unit_peak_gb
    # Automatic and explicit payload forecasts must avoid the
    # submitting host, even when a request ledger happens to be active there.
    with execution_scope(dict(factorization='compressed', compressed_storage_mib=storage)), \
         patch.object(mb, 'current', side_effect=AssertionError('head-host ledger read')), \
         patch.object(solver, '_solve_memory_limit_gb', side_effect=AssertionError('head-host RAM read')), \
         patch('ghost_backend.compressed.hmatrix.selected', return_value=True):
        # Use real structural forecasts (without a numerical operator).
        plan = runtime.planned_forecast(100, 200, 3, 3, 1, {}, submission_planning=True)
        assert plan['storage_policy'] == ('submission_payload_forecast' if storage == 0 else 'explicit_payload_cap')
        assert unit_peak_gb(100, 1, 1.5) > 0


def test_submission_cannot_activate_runtime_plan():
    with pytest.raises(ValueError, match='submission forecast'):
        solver._estimate_memory_gb(100, False, submission_planning=True, activate_memory_plan=True)
