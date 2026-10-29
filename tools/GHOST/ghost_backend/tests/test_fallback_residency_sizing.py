"""Automatic payload sizing must include extra live residency before admission."""
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import pytest
from ghost_backend.compressed import runtime,memory
from ghost_backend.execution import memory_budget as mb
from ghost_backend.execution.options import execution_scope
from ghost_backend.twod import solver
from test_request_memory_budget import simulated,GIB

SAMPLE=dict(operator_bytes=2*GIB,operator_allowance_bytes=2*GIB,method='test',samples=1,sampled=True,groups=16)

def test_extra_live_residency_reduces_payload_before_fallback_decision():
    with simulated(cap=6.) as (_,ledger),patch('ghost_backend.compressed.worker_pool.forecast_bytes',return_value=2*GIB):
        raw=runtime.planned_forecast(4000,8000,361,256,4,{'compressed_storage':SAMPLE,'basis_width':4})
        live=raw['process_geometry_bytes']+GIB
        assert raw['peak_bytes']+GIB>6*GIB  # Old post-sizing adjustment refused.
        source=SimpleNamespace(n=8000,mesh=SimpleNamespace(nodes=range(4000)))
        with patch.object(memory,'sample_operator',return_value=SAMPLE),patch.object(solver,'_process_rss_bytes',return_value=live),patch.object(solver,'_solve_memory_limit_gb',return_value=6.),patch('ghost_backend.compressed.worker_pool.retained_bytes',return_value=0),patch('ghost_backend.compressed.worker_pool.release_idle',return_value=0),patch('ghost_backend.twod.operators.get_assembly_threads',return_value=4):
            plan=runtime.admit_tile_fallback(source,np.empty((0,2)),'rank')['forecasts'][0]
        assert plan['peak_bytes']<=6*GIB
        assert plan['storage_limit_bytes']==raw['storage_limit_bytes']-GIB
        assert plan['process_geometry_bytes']==live
        assert ledger.plan['process_geometry_bytes']==live
        assert runtime.storage_budget()==plan['storage_limit_bytes']
        # Later reload checks must retain the extra allocation allowance too.
        with pytest.raises(MemoryError):mb.admit_reload(3*GIB,workspace=0)


def test_explicit_storage_is_not_silently_reduced_and_oversized_workspace_still_fails():
    with simulated(cap=6.),patch('ghost_backend.compressed.worker_pool.forecast_bytes',return_value=2*GIB):
        resources={'compressed_storage':SAMPLE,'basis_width':4}
        with execution_scope(dict(factorization='compressed',compressed_storage_mib=4096,ram_budget_gib=6.)):
            explicit=runtime.planned_forecast(4000,8000,361,256,4,resources,live_residency_bytes=4*GIB)
        assert explicit['storage_limit_bytes']==4*GIB and explicit['peak_bytes']>6*GIB
        oversized=runtime.planned_forecast(4000,8000,361,256,4,resources,live_residency_bytes=7*GIB)
        assert oversized['storage_limit_bytes']==0 and oversized['peak_bytes']>6*GIB


def test_live_adjustment_does_not_change_a_speculative_active_plan():
    with simulated(cap=6.) as (_,ledger):
        previous={'nonstorage_phase_bytes':dict(assembly=GIB,factorization=GIB,solve=GIB)}
        mb.record_plan(previous)
        runtime.planned_forecast(100,200,3,3,1,{},live_residency_bytes=2*GIB)
        assert ledger.plan is previous
