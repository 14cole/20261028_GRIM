"""Ownership, pressure and stable allowances at the request RAM boundary."""
import gc
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from ghost_backend.execution import memory_budget as mb
from ghost_backend.execution.options import execution_scope, memory_allocation_scope
from ghost_backend.compressed import runtime
from ghost_backend.compressed.factor import CompressedFactor
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
from ghost_backend.twod import solver
from ghost_backend.hpc import scheduler

GIB=1024**3


class Owned:
    def __init__(self,size):
        self.bytes=int(size*GIB)
        self.row_norm=np.ones(1);self.row_error=np.zeros(1)
        self.n=1;self.evidence={};self.checkpoint=lambda:None


@contextmanager
def simulated(available=24.,cap=None,commit=None):
    state=dict(available=available,rss=0,private=0,commit=commit)
    with patch.object(solver,'_detect_available_gb',side_effect=lambda:state['available']), \
         patch.object(mb,'process_memory',side_effect=lambda:(state['rss'],state['private'])), \
         patch('ghost_backend.execution.memory.windows_available_commit_bytes',side_effect=lambda:state['commit']), \
         execution_scope(dict(factorization='compressed',compressed_storage_mib=0,ram_budget_gib=cap)):
        with mb.scope() as ledger:
            yield state,ledger


@pytest.mark.parametrize('kind',[CompressedFactor,HMatrixFactor])
def test_own_operator_does_not_shrink_storage_or_reject_fitting_inverse(kind):
    with simulated() as (live,ledger):
        before=runtime.storage_budget()
        assert before/GIB==pytest.approx(12.96)
        operator=Owned(10);mb.register(operator)
        live.update(available=14.,rss=10*GIB,private=10*GIB)
        assert runtime.storage_budget()==before
        assert solver._solve_memory_limit_gb()==pytest.approx(21.6)
        with patch.object(kind,'_fresh_build'):
            factor=kind(operator,check_precision=False)
        assert factor.budget/GIB==pytest.approx(2.96)
        ledger.require(18.,'later polarization')


def test_external_pressure_still_refuses_and_reports_binding_constraint():
    with simulated() as (live,ledger):
        ledger.require(18.,'initial')
        operator=Owned(8);mb.register(operator)
        live.update(available=6.,rss=8*GIB,private=8*GIB)
        with pytest.raises(MemoryError,match='live_physical_ram'):
            ledger.require(18.,'refined mesh')
        assert ledger.last['limit_gib']==pytest.approx(11.6)


def test_unrelated_process_growth_never_receives_ownership_credit():
    with simulated() as (live,ledger):
        ledger.stable()
        live.update(available=14.,rss=10*GIB,private=10*GIB)
        assert ledger.owned()==(0.,0.,0.)
        assert ledger.limit()==pytest.approx(11.6)


def test_paged_or_unmaterialized_payload_cannot_get_full_resident_credit():
    with simulated() as (live,ledger):
        operator=Owned(10);mb.register(operator)
        live.update(rss=2*GIB,private=10*GIB,available=22.)
        assert ledger.owned()==(10.,2.,10.)
        del operator;gc.collect()
        assert ledger.owned()==(0.,0.,0.)


def test_explicit_and_parent_caps_survive_resident_credit_and_nested_scopes():
    with simulated(cap=12.) as (live,ledger):
        assert ledger.stable()==12.
        operator=Owned(10);mb.register(operator)
        live.update(rss=10*GIB,private=10*GIB,available=14.)
        with memory_allocation_scope(11.),mb.scope() as child:
            assert child is ledger
            assert solver._solve_memory_limit_gb()==11.
            assert runtime.storage_budget()/GIB==pytest.approx(6.6)
            with pytest.raises(MemoryError,match='11.000'):
                ledger.require(11.5,'nested factor')
        assert ledger.stable()==12.
    assert mb.current() is None


@pytest.mark.parametrize('available,expected',[(None,12.),(0.,0.),(.25,.225)])
def test_zero_unknown_and_small_allowance_are_distinct(available,expected):
    with simulated(available,12.) as (_,ledger):
        assert ledger.limit()==pytest.approx(expected)
        assert runtime.storage_budget() <= expected*GIB


def test_zero_outside_request_cannot_be_overridden_by_explicit_cap():
    with execution_scope(dict(ram_budget_gib=12.)),patch.object(solver,'_detect_available_gb',return_value=0.):
        assert solver._solve_memory_limit_gb()==0.


def test_commit_pressure_refuses_despite_free_physical_ram():
    with simulated(commit=20*GIB) as (live,ledger):
        assert ledger.stable()==18.
        live['commit']=3*GIB
        with pytest.raises(MemoryError,match='live_commit_headroom'):
            ledger.require(2.,'inverse construction')


def test_phase_guard_rechecks_pressure_after_main_admission():
    with simulated() as (live,ledger):
        ledger.require(10.,'initial')
        mb.record_plan(dict(phase_bytes=dict(factorization=10*GIB,solve=11*GIB)))
        live['available']=5.
        with pytest.raises(MemoryError,match='Compressed factorization'):
            mb.admit_phase('factorization')


def test_simultaneous_request_reservations_do_not_spend_the_same_free_ram():
    with simulated(cap=8.) as (_,first):
        assert first.stable()==8.
        with mb._STATE.override(None):
            with simulated(cap=24.) as (_,second):
                assert second.stable()==pytest.approx(13.6)
        assert first.stable()==8.
    with simulated(cap=24.) as (_,fresh):
        assert fresh.stable()==pytest.approx(21.6)


@pytest.mark.parametrize('fraction',[.70,.80,.85,.90])
def test_ownership_and_headroom_at_near_limit_reservations(fraction):
    with simulated(available=10.) as (live,ledger):
        ledger.require(10*fraction,'initial')
        operator=Owned(10*fraction);mb.register(operator)
        live.update(available=10-10*fraction,rss=int(10*fraction*GIB),private=int(10*fraction*GIB))
        ledger.require(10*fraction,'already owned')
        with pytest.raises(MemoryError):ledger.require(9.01,'exceeds 90 percent')


def test_local_budget_uses_available_ninety_percent_without_a_one_gib_floor():
    with patch.object(scheduler,'detect_memory_gb',return_value=32.):
        for available in (31.,24.,.25,0.):
            with patch.object(scheduler,'detect_available_memory_gb',return_value=available):
                assert scheduler.local_memory_budget_gb(.9)[0]==pytest.approx(.9*available)
    with patch('psutil.virtual_memory',return_value=SimpleNamespace(available=0)):
        assert scheduler.detect_available_memory_gb()==0.


def test_worker_credit_uses_unique_residency_not_reserved_or_shared_pages():
    class Workers:
        def memory_snapshot(self):
            return dict(complete=True,unique_resident_bytes=GIB,private_bytes=2*GIB,
                        rss_bytes=3*GIB,reservation_bytes=4*GIB)
    with simulated() as (_,ledger):
        pool=Workers();mb.register(pool,'workers')
        assert ledger.owned()==(0.,1.,2.)
        assert mb.report()['worker_samples'][-1]['reservation_bytes']==4*GIB


def test_direct_frequency_sweep_resets_batch_only_between_independent_systems():
    from ghost_backend.execution import angle_batch
    from ghost_backend.execution.cpu import configured_batch_size
    batches=[]
    def solve(**kwargs):
        batches.append(configured_batch_size())
        angle_batch._RECOVERY.get()['limit']=32
        return kwargs['frequencies_ghz'][0]
    with execution_scope(dict(factorization='compressed',angle_batch_size=256)),angle_batch.scope(), \
         patch.object(solver,'_merge_frequency_results',side_effect=lambda values,frequencies:list(values)):
        result=solver._frequency_local_co_solve(solve,dict(frequencies_ghz=[15.,1.]))
    assert result==[15.,1.] and batches==[256,256]


def test_spooled_partner_ledger_excludes_disk_and_reload_rechecks_pressure(tmp_path):
    from ghost_backend.compressed.polarization_cache import SpooledOperator
    from test_compressed_path import Exact
    source=Exact(np.eye(32,dtype=complex))
    with simulated() as (live,ledger):
        disk=SpooledOperator(source,np.arange(32)[:,None],tile=16,directory=tmp_path)
        assert disk.spool_bytes>0
        assert disk.resident_bytes==disk.bytes-disk.spool_bytes
        path=disk.path
        live['available']=0.
        with pytest.raises(MemoryError,match='spool reload'):
            disk.load()
        assert disk.file is None and not path.exists()
        assert not disk.tiles


def test_memory_evidence_is_bounded_for_long_sweeps():
    with simulated() as (_,ledger):
        for _ in range(100):ledger.require(1.,'solve')
        report=mb.report()
        assert report['total_checks']==100
        assert len(report['checks'])==64 and report['omitted_earlier_checks']==36
