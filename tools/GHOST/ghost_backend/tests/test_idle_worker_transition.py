"""Worker release follows actual backend transitions, never speculative forecasts."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from ghost_backend.compressed import runtime, worker_pool, hmatrix
from ghost_backend.execution import cpu
from ghost_backend.execution.options import execution_scope
from ghost_backend.twod import solver
from ghost_backend.twod.preparation import preparation_scope, run_resources
from test_request_memory_budget import simulated, GIB


class Pool:
    closed=False
    busy=False
    reserved_bytes=2*GIB
    def close(self):self.closed=True


def test_idle_team_is_closed_before_pricing_hierarchical_workspace():
    pool=Pool();state=SimpleNamespace(memory_estimates=[])
    with preparation_scope(),patch.object(hmatrix,'selected',return_value=True), \
         patch.object(cpu,'current_state',return_value=state):
        run_resources()['compressed_tile_workers']=pool
        assert runtime.release_obsolete_tile_workers({'hmatrix_storage':{'model':True}},50000)==2*GIB
        assert pool.closed and worker_pool.retained_bytes()==0
        assert state.memory_estimates[-1]['released_allowance_bytes']==2*GIB
        assert runtime.release_obsolete_tile_workers({'hmatrix_storage':{'model':True}},50000)==0


@pytest.mark.parametrize('case',['busy','not_selected','no_model','unsupported'])
def test_useful_or_busy_workers_are_preserved(case):
    pool=Pool();pool.busy=case=='busy'
    resources={} if case=='no_model' else {'hmatrix_storage':{'model':True}}
    with preparation_scope(),patch.object(hmatrix,'selected',return_value=case!='not_selected'), \
         patch.object(hmatrix,'configuration_unsupported',return_value='unsupported' if case=='unsupported' else None):
        run_resources()['compressed_tile_workers']=pool
        assert runtime.release_obsolete_tile_workers(resources,50000)==0
        assert not pool.closed


def test_speculative_forecast_never_releases_but_real_admission_does():
    with simulated(cap=6.),patch.object(runtime,'release_obsolete_tile_workers',return_value=0) as release:
        solver._estimate_memory_gb(100,False,system_dofs=100,dense_resources={})
        release.assert_not_called()
        solver._estimate_memory_gb(100,False,system_dofs=100,dense_resources={},activate_memory_plan=True)
        release.assert_called_once()


def test_hierarchical_forecast_removes_only_the_released_worker_allowance():
    model=dict(operator_bytes=GIB//2,inverse_bytes=GIB//2,inverse_peak_bytes=GIB,
        assembly_workspace_bytes=GIB//8,method='test',coefficients=1,inverse_rank=1)
    resources={'hmatrix_storage':model}
    pool=Pool()
    with simulated(cap=6.),preparation_scope(),patch.object(hmatrix,'selected',return_value=True):
        run_resources()['compressed_tile_workers']=pool
        before=runtime.planned_forecast(100,200,361,256,4,resources)
        runtime.release_obsolete_tile_workers(resources,200)
        after=runtime.planned_forecast(100,200,361,256,4,resources)
        assert before['retained_worker_allowance_bytes']==2*GIB
        assert after['retained_worker_allowance_bytes']==0
        assert after['storage_limit_bytes']-before['storage_limit_bytes']==2*GIB
        assert before['peak_bytes']-after['peak_bytes']==2*GIB


def test_later_tile_mesh_recreates_a_released_team():
    class Replacement(Pool):
        def __init__(self,workers):self.workers=workers;self.closed=False;self.busy=False
    with preparation_scope(),patch.object(hmatrix,'selected',return_value=True):
        old=Replacement(4);run_resources()['compressed_tile_workers']=old
        runtime.release_obsolete_tile_workers({'hmatrix_storage':{'model':True}},50000)
        with patch.object(worker_pool,'WorkerPool',Replacement):
            new=worker_pool.acquire(4,lease=True)
        assert old.closed and new is not old and new.busy
        worker_pool.release_lease(new)
