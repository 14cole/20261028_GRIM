"""Budget recovery must preserve all angles, accuracy gates and working factors."""
from types import SimpleNamespace
from unittest import mock
import numpy as np
import pytest

from ghost_backend.compressed import memory
from ghost_backend.compressed.factor import CompressedFactor, GMRES_BATCH
from ghost_backend.execution.options import validate_options, execution_scope
from ghost_backend.execution import selection


@pytest.mark.parametrize('batch', [1, 8, 16, 64, 256])
def test_forecast_covers_observed_gmres_basis_and_work(batch):
    n, count = 100, min(batch, GMRES_BATCH)
    factor = CompressedFactor.__new__(CompressedFactor)
    factor.checkpoint = lambda: None
    factor.a = SimpleNamespace(matmul=lambda b, trans: b.copy(),
                               row_norm=np.ones(n), column_norm=np.ones(n))
    factor.factor = SimpleNamespace(apply=lambda b, **kwargs: b.copy())
    original = np.empty
    allocations = []
    def track(*args, **kwargs):
        value = original(*args, **kwargs)
        allocations.append(value.nbytes)
        return value
    with mock.patch('ghost_backend.compressed.factor.np.empty', side_effect=track):
        x = factor._gmres(np.ones((n,count),complex),np.zeros((n,count),complex),0)
    np.testing.assert_allclose(x, 1, rtol=1e-14, atol=1e-14)
    assert memory.correction_workspace(n,batch) >= sum(allocations)
    with mock.patch('ghost_backend.compressed.worker_pool.forecast_bytes', return_value=0):
        plan=memory.forecast(n,n,batch,batch,1,1024**3)
    assert plan['gmres_workspace_bytes'] == memory.correction_workspace(n,batch)
    assert plan['phase_bytes']['solve'] >= plan['rhs_workspace_bytes']+plan['gmres_workspace_bytes']


def upgrade_fixture():
    f=CompressedFactor.__new__(CompressedFactor)
    f.factor=SimpleNamespace(bytes=16*memory.MIB)
    f.budget=64*memory.MIB
    f.tolerance=1e-8
    f.event={}
    return f


@pytest.mark.parametrize('outcome', ['success','memory','rank','cancel'])
def test_upgrade_preserves_working_inverse_and_budget_on_failure(outcome):
    from ghost_backend.linalg.hierarchical import HierarchicalRejected
    f=upgrade_fixture(); old=f.factor
    def build(tolerance):
        assert f.budget == 48*memory.MIB
        f.factor=SimpleNamespace(bytes=24*memory.MIB)
        f.tolerance=tolerance
        if outcome=='memory':raise MemoryError('full')
        if outcome=='rank':raise HierarchicalRejected('rank')
        if outcome=='cancel':raise InterruptedError('cancel')
    with mock.patch('ghost_backend.twod.solver._process_rss_bytes', return_value=0), \
         mock.patch('ghost_backend.twod.solver._solve_memory_limit_gb', return_value=2), \
         mock.patch('ghost_backend.compressed.worker_pool.retained_bytes', return_value=0), \
         mock.patch.object(f,'_build',side_effect=build) as builder:
        if outcome=='cancel':
            with pytest.raises(InterruptedError):f._upgrade_preconditioner()
        else:
            assert f._upgrade_preconditioner() == (outcome=='success')
        assert not f._upgrade_preconditioner()
        assert builder.call_count==1
    assert f.budget==64*memory.MIB
    if outcome!='success':
        assert f.factor is old and f.tolerance==1e-8
    else:
        assert f.factor is not old and f.tolerance==1e-10


def test_upgrade_refuses_without_construction_headroom():
    f=upgrade_fixture()
    with mock.patch('ghost_backend.twod.solver._process_rss_bytes',return_value=100*memory.MIB), \
         mock.patch('ghost_backend.twod.solver._solve_memory_limit_gb',return_value=.12), \
         mock.patch('ghost_backend.compressed.worker_pool.retained_bytes',return_value=0), \
         mock.patch.object(f,'_build') as build:
        assert not f._upgrade_preconditioner()
        build.assert_not_called()


def test_slow_refinement_restarts_once_with_stronger_inverse():
    f=upgrade_fixture()
    f.event.update(max_refinements=0,refinement_steps=0,gmres_columns=0)
    f.checkpoint=lambda:None
    f.a=SimpleNamespace(matmul=lambda b, trans:b.copy(),row_norm=np.ones(5),column_norm=np.ones(5))
    f.factor=SimpleNamespace(apply=lambda b,**kw:.9*b)
    def upgrade():
        f.factor=SimpleNamespace(apply=lambda b,**kw:b.copy())
        return True
    with mock.patch.object(f,'_upgrade_preconditioner',side_effect=upgrade) as upgrade:
        x,residual=f._refine(np.ones((5,2)),0)
    upgrade.assert_called_once()
    np.testing.assert_array_equal(x,np.ones((5,2)))
    np.testing.assert_array_equal(residual,np.zeros((5,2)))


def forecast_fixture():
    options=validate_options(dict(factorization='adaptive',angle_batch_size=256,ram_budget_gib=1))
    resource=dict(nodes=100,system_dofs=100,n_regions=1,operator_matrices=0)
    result=dict(candidates={m:dict(peak_gb=3.,cost=1.) for m in ('dense','compressed')},
                admission_budget_gib=1.,meshes=[dict(resources=resource)])
    return options,resource,result


def test_batch_recovery_reprices_and_keeps_every_angle():
    options,resource,result=forecast_fixture()
    arguments=dict(elevations_deg=list(range(361)))
    from ghost_backend.execution.cpu import configured_batch_size
    def estimate(*args,**kwargs):
        assert kwargs['n_rhs']==361
        return .1+configured_batch_size()*.01
    with mock.patch('ghost_backend.twod.solver._estimate_memory_gb',side_effect=estimate), \
         mock.patch('ghost_backend.twod.solver._solve_memory_limit_gb',return_value=1.), \
         mock.patch('ghost_backend.compressed.worker_pool.release_idle',return_value=0), \
         mock.patch('ghost_backend.execution.selection.relative_cost',return_value=1.):
        selection._recover_memory_forecast(result,[(resource,options)],arguments,options)
    assert result['angle_batch_size']==64
    assert result['resource_adjustment']['requested_angle_batch_size']==256
    assert result['resource_adjustment']['rejected_batch_sizes']==[128]
    assert result['candidates']['compressed']['peak_gb']==pytest.approx(.74)
    assert len(arguments['elevations_deg'])==361
    assert options['angle_batch_size']==256


def test_batch_recovery_does_not_admit_an_oversized_operator():
    options,resource,result=forecast_fixture()
    with mock.patch('ghost_backend.twod.solver._estimate_memory_gb',return_value=2.), \
         mock.patch('ghost_backend.twod.solver._solve_memory_limit_gb',return_value=1.), \
         mock.patch('ghost_backend.compressed.worker_pool.release_idle',return_value=0), \
         mock.patch('ghost_backend.execution.selection.relative_cost',return_value=1.):
        with pytest.raises(MemoryError):
            selection._recover_memory_forecast(result,[(resource,options)],dict(elevations_deg=[0]),options)


def test_worker_release_never_closes_a_busy_pool():
    from ghost_backend.compressed.worker_pool import release_idle
    pool=SimpleNamespace(closed=False,busy=True,reserved_bytes=123,close=mock.Mock())
    resources={'compressed_tile_workers':pool}
    with mock.patch('ghost_backend.twod.preparation.run_resources',return_value=resources):
        assert release_idle()==0
        pool.close.assert_not_called()
        pool.busy=False
        assert release_idle()==123
        pool.close.assert_called_once()
        assert not resources


@pytest.mark.parametrize('fits',[False,True])
def test_tile_fallback_is_repriced_before_building_workers(fits):
    from ghost_backend.compressed.runtime import admit_tile_fallback
    source=SimpleNamespace(n=10,mesh=SimpleNamespace(nodes=list(range(10))))
    sample=dict(operator_bytes=100,operator_allowance_bytes=100,method='test',samples=1,sampled=True)
    plan=dict(peak_bytes=memory.GIB*(.5 if fits else 2),process_geometry_bytes=100,
              phase_bytes={'assembly':memory.GIB*(.5 if fits else 2)})
    with execution_scope(validate_options(dict(ram_budget_gib=1))), \
         mock.patch('ghost_backend.compressed.memory.sample_operator',return_value=sample), \
         mock.patch('ghost_backend.compressed.memory.forecast',side_effect=lambda *a,**k:dict(plan)), \
         mock.patch('ghost_backend.twod.solver._process_rss_bytes',return_value=0), \
         mock.patch('ghost_backend.twod.solver._solve_memory_limit_gb',return_value=1.), \
         mock.patch('ghost_backend.compressed.worker_pool.retained_bytes',return_value=0), \
         mock.patch('ghost_backend.compressed.worker_pool.release_idle',return_value=0), \
         mock.patch('ghost_backend.compressed.worker_pool.acquire') as workers:
        if fits:
            assert admit_tile_fallback(source,np.zeros((10,2)),'rank')['forecasts'][0]['peak_bytes']==memory.GIB*.5
        else:
            with pytest.raises(MemoryError,match='Hierarchical-to-tile fallback'):
                admit_tile_fallback(source,np.zeros((10,2)),'rank')
        workers.assert_not_called()


@pytest.mark.parametrize('reason', ['rank', 'sampled row error', 'storage'])
def test_rejected_hmatrix_releases_failed_arrays_before_tile_admission(reason):
    import weakref
    from ghost_backend.compressed import runtime, hmatrix
    source=SimpleNamespace(n=20,mesh=SimpleNamespace(nodes=list(range(20))))
    retained=[]
    def reject(*args,**kwargs):
        scratch=np.ones((20,20),complex)
        retained.append(weakref.ref(scratch))
        error=MemoryError if reason=='storage' else hmatrix.HMatrixRejected
        raise error(reason)
    def refuse(*args):
        assert retained[0]() is None
        raise MemoryError('tile admission refused')
    with mock.patch.object(hmatrix,'selected',return_value=True), \
         mock.patch.object(hmatrix,'unsupported',return_value=None), \
         mock.patch.object(hmatrix,'support_radius',return_value=np.zeros(20)), \
         mock.patch.object(hmatrix,'HMatrixOperator',side_effect=reject), \
         mock.patch.object(runtime,'admit_tile_fallback',side_effect=refuse), \
         mock.patch('ghost_backend.compressed.operator.StreamedOperator') as tiles:
        with pytest.raises(MemoryError,match='tile admission refused'):
            runtime.build(source,np.zeros((20,2)))
        tiles.assert_not_called()


def test_sweep_reprices_common_batch_before_ranking_incompatible_peaks():
    from ghost_backend.twod.preparation import preparation_scope
    options,resource,_=forecast_fixture()
    resource.update(polynomial_degree=1)
    def part(arguments, options, certified, checkpoint, records):
        first=arguments['frequencies_ghz']==[1.]
        records.append((resource,options))
        return dict(candidates=dict(dense=dict(cost=1.,peak_gb=.5 if first else 2.),
            compressed=dict(cost=1.,peak_gb=2. if first else .5)),
            angle_batch_size=128 if first else 64, dense_peak_gib=.5 if first else 2.,
            meshes=[dict(resources=resource,polynomial_degree=1)])
    from ghost_backend.execution.cpu import configured_batch_size
    with preparation_scope(), \
         mock.patch.object(selection,'_forecast_backend',side_effect=part), \
         mock.patch('ghost_backend.twod.solver._solve_memory_limit_gb',return_value=1.), \
         mock.patch('ghost_backend.twod.solver._estimate_memory_gb',side_effect=lambda *a,**k:configured_batch_size()/128), \
         mock.patch.object(selection,'relative_cost',return_value=1.):
        result=selection.select_backend(dict(frequencies_ghz=[1.,2.],elevations_deg=list(range(361))),options)
    assert result['angle_batch_size']==64
    assert result['candidates']['dense']['peak_gb']==.5
    assert result['resource_adjustment']['requested_angle_batch_size']==256
