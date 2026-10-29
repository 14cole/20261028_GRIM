"""Learned policies must remain optional, admitted, owned and observable."""
from types import SimpleNamespace
from unittest import mock
import contextvars
import threading
import numpy as np
import pytest
from ghost_backend.compressed import preconditioner_hints as hints, worker_pool
from ghost_backend.compressed.factor import CompressedFactor
from ghost_backend.hpc import runtime_snapshot
from ghost_backend.twod.preparation import preparation_scope

MIB=1024**2


class Operator(SimpleNamespace):
    def __len__(self):return self.n


def factor(n=100):
    f=CompressedFactor.__new__(CompressedFactor)
    f.a=Operator(n=n,evidence={'operator':'hmatrix'},oracle=SimpleNamespace(kind='dielectric'))
    f.factor=SimpleNamespace(bytes=16*MIB)
    f.tolerance=1e-10
    f.budget=256*MIB
    f.event={}
    return f


@pytest.fixture
def admitted():
    state=SimpleNamespace(current_resources={'formulation':'single_dielectric'})
    with mock.patch('ghost_backend.execution.cpu.current_state',return_value=state), \
         mock.patch('ghost_backend.twod.solver._process_rss_bytes',return_value=0), \
         mock.patch('ghost_backend.twod.solver._solve_memory_limit_gb',return_value=2), \
         mock.patch.object(worker_pool,'retained_bytes',return_value=0):
        yield state


def test_hint_scales_and_reprices_then_builds_once(admitted):
    with hints.scope([1.],{'segments':[]}):
        hints.remember(factor())
        f=factor(150)
        def build(tolerance):
            assert tolerance==1e-10 and f.budget==72*MIB
            f.factor=SimpleNamespace(bytes=36*MIB)
        with mock.patch.object(f,'_build',side_effect=build) as build:
            f._fresh_build()
            build.assert_called_once_with(1e-10)
        assert f.budget==256*MIB
        assert f.event['preconditioner_hint']['accepted']
        assert f.event['preconditioner_hint']['construction_allowance_bytes']==108*MIB


@pytest.mark.parametrize('kind',['frequency','geometry','material','units','sweep','formulation','new_request'])
def test_hint_does_not_cross_incompatible_scope(admitted,kind):
    geometry={'segments':['first']}
    with hints.scope([1.],geometry,'materials','meters'):
        hints.remember(factor())
        if kind=='formulation':
            admitted.current_resources['formulation']='multi_region'
            assert not hints.try_build(factor())
        elif kind!='new_request':
            args=([2.] if kind=='frequency' else [1.,2.] if kind=='sweep' else [1.],
                {'segments':['second']} if kind=='geometry' else geometry,
                'other' if kind=='material' else 'materials','inches' if kind=='units' else 'meters')
            with hints.scope(*args):
                assert not hints.try_build(factor())
    with hints.scope([1.],geometry,'materials','meters'):
        assert not hints.try_build(factor())


def test_adaptive_tags_preserve_physical_request_identity(admitted):
    with hints.scope([1.],{'segments':[]}):
        hints.remember(factor())
        with hints.scope([1.],{'segments':[],'_2d_hp_coarsening':2,'_2d_hp_refinements':{}}):
            f=factor()
            with mock.patch.object(f,'_build'):
                assert hints.try_build(f)


@pytest.mark.parametrize('failure',[MemoryError,RuntimeWarning])
def test_hint_build_rejection_restores_standard_policy(admitted,failure):
    with hints.scope([1.]):
        hints.remember(factor())
        f=factor()
        calls=[]
        def build(tolerance):
            calls.append(tolerance)
            if tolerance==1e-10:
                f.factor=SimpleNamespace(bytes=123)
                raise failure('hint rejected')
            assert f.budget==256*MIB
            f.tolerance=tolerance
            f.factor=SimpleNamespace(bytes=20*MIB)
        with mock.patch.object(f,'_build',side_effect=build):f._fresh_build()
        assert calls==[1e-10,1e-8]
        assert not hints.try_build(factor())
        assert not f.event['preconditioner_hint']['accepted']


def test_hint_cancellation_restores_budget_and_propagates(admitted):
    with hints.scope([1.]):
        hints.remember(factor())
        f=factor()
        with mock.patch.object(f,'_build',side_effect=InterruptedError('stop')):
            with pytest.raises(InterruptedError):hints.try_build(f)
        assert f.budget==256*MIB and f.factor is None


def test_hint_without_headroom_is_not_built(admitted):
    with hints.scope([1.]):
        hints.remember(factor())
        f=factor();f.budget=MIB
        with mock.patch.object(f,'_build') as build:
            assert not hints.try_build(f)
        build.assert_not_called()


def test_hint_solve_rejection_falls_back_once(admitted):
    from ghost_backend.linalg.hierarchical import HierarchicalRejected
    with hints.scope([1.]):
        hints.remember(factor())
        f=factor(2)
        f.a.shape=(2,2)
        f.event=dict(preconditioner_hint={'accepted':True},max_backward_error=0.)
        f._hint_attempted=True
        def fresh():f.tolerance=1e-8
        with mock.patch.object(f,'_refine',side_effect=[HierarchicalRejected('stall'),(np.ones((2,1)),np.zeros((2,1)))]), \
             mock.patch.object(f,'_fresh_build',side_effect=fresh) as rebuild, \
             mock.patch.object(f,'physical_errors',return_value=np.zeros(1)):
            np.testing.assert_array_equal(f.inverse(np.ones(2)),np.ones(2))
        rebuild.assert_called_once()
        assert f._upgrade_attempted
        assert not hints.try_build(factor())


def test_paired_admission_retains_both_polarizations():
    from ghost_backend.compressed.runtime import record_paired_admission
    pair=[SimpleNamespace(evidence={}),SimpleNamespace(evidence={})]
    event=dict(reason='rank rejected',forecasts=[{'peak_bytes':123}])
    record_paired_admission(pair,event)
    for op,pol in zip(pair,('TE','TM')):
        assert op.evidence['fallback_admission']['polarization']==pol
        assert op.evidence['fallback_admission']['forecasts']==event['forecasts']
        assert op.evidence['hmatrix_fallback']==event['reason']
    assert 'polarization' not in event


def test_shared_context_cannot_acquire_or_release_an_active_pool(tmp_path):
    with preparation_scope():
        pool=worker_pool.acquire(1,lease=True)
        results=[]
        def contender():
            results.append(worker_pool.release_idle())
            try:worker_pool.acquire(2,lease=True)
            except RuntimeError:results.append('busy')
        thread=threading.Thread(target=contextvars.copy_context().run,args=(contender,))
        thread.start();thread.join(timeout=5)
        assert not thread.is_alive() and results==[0,'busy']
        assert pool.busy and not pool.closed
        worker_pool.release_lease(pool)
        assert worker_pool.release_idle()>0 and pool.closed
        replacement=worker_pool.acquire(1,lease=True)
        assert replacement is not pool
        worker_pool.release_lease(replacement,failed=True)
        assert replacement.closed and not replacement.busy


def test_preparation_failure_releases_the_acquired_lease():
    from ghost_backend.compressed.tile_processes import compressed_tiles
    pool=SimpleNamespace(busy=True,prepare=mock.Mock(side_effect=InterruptedError('cancel')),
                         close=mock.Mock())
    with mock.patch.object(worker_pool,'acquire',return_value=pool) as acquire:
        with pytest.raises(InterruptedError):
            next(compressed_tiles(SimpleNamespace(),[SimpleNamespace(groups=[np.array([0])])],2,b'data',lambda:None))
    acquire.assert_called_once_with(2,lease=True)
    pool.close.assert_called_once()
    assert not pool.busy


def permission_error():
    error=PermissionError('temporary sharing violation')
    error.winerror=32
    return error


@pytest.mark.parametrize('outcome',['success','exhausted','destination','other'])
def test_publication_retry_is_bounded_and_never_overwrites(outcome):
    # Patch only the publication primitive; no fake platform Path objects.
    count=[0]
    def rename(*args):
        count[0]+=1
        if outcome=='other':raise OSError('disk error')
        if outcome!='success' or count[0]<3:raise permission_error()
    with mock.patch.object(runtime_snapshot,'_WINDOWS_RENAME_RETRY',True), \
         mock.patch.object(runtime_snapshot.os,'rename',side_effect=rename), \
         mock.patch.object(runtime_snapshot.os.path,'lexists',side_effect=lambda path:outcome=='destination' and count[0]>0), \
         mock.patch.object(runtime_snapshot.time,'sleep') as sleep:
        if outcome=='success':runtime_snapshot._publish_directory('source','destination')
        else:
            with pytest.raises(FileExistsError if outcome=='destination' else PermissionError if outcome=='exhausted' else OSError):
                runtime_snapshot._publish_directory('source','destination')
    assert count[0]=={'success':3,'exhausted':4,'destination':1,'other':1}[outcome]
    assert sleep.call_count=={'success':2,'exhausted':3,'destination':1,'other':0}[outcome]


def test_failed_publication_cleans_verified_staging_and_lock(tmp_path):
    from test_hpc_runtime_snapshot import source_tree
    source=source_tree(tmp_path/'source');run=tmp_path/'run'
    with mock.patch.object(runtime_snapshot,'_WINDOWS_RENAME_RETRY',True), \
         mock.patch.object(runtime_snapshot.os,'rename',side_effect=permission_error()) as rename, \
         mock.patch.object(runtime_snapshot.time,'sleep'):
        with pytest.raises(PermissionError):runtime_snapshot.snapshot_backend_runtime(source,run)
    assert rename.call_count==4
    assert not (run/'runtime').exists()
    assert not (run/'.runtime-snapshot.lock').exists()
    assert not list(run.glob('.runtime-staging-*'))
    assert (source/'bor/solver.py').read_text()=='VALUE = 17\n'


def test_small_batch_notice_counts_passes_without_inventing_time():
    from ghost_backend.execution.selection import describe_batch_adjustment
    result=dict(angle_batch_size=1,resource_adjustment={'requested_angle_batch_size':256})
    describe_batch_adjustment(result,361)
    event=result['resource_adjustment']
    assert event['requested_angle_batches']==2 and event['effective_angle_batches']==361
    assert event['predicted_extra_seconds'] is None
    assert 'factor is reused' in event['notice']


def test_exhausted_admission_reports_formulation_and_final_batch():
    from test_large_geometry_resources import forecast_fixture
    from ghost_backend.execution import selection
    options,resource,result=forecast_fixture()
    resource['formulation']='single_dielectric'
    with mock.patch('ghost_backend.twod.solver._estimate_memory_gb',return_value=2.), \
         mock.patch('ghost_backend.twod.solver._solve_memory_limit_gb',return_value=1.), \
         mock.patch.object(worker_pool,'release_idle',return_value=0), \
         mock.patch.object(selection,'relative_cost',return_value=1.):
        with pytest.raises(MemoryError,match='Formulations: single_dielectric. Final angle batch: 1.') as error:
            selection._recover_memory_forecast(result,[(resource,options)],dict(elevations_deg=[0]),options)
    assert isinstance(error.value.__cause__,MemoryError)


def test_reference_mesh_fallback_uses_newly_admitted_batch():
    from ghost_backend.execution import options as O
    from ghost_backend.twod import adaptivity
    actual=[];progress=[]
    def solve(*a,**k):
        actual.append(O.current_options()['angle_batch_size'])
        return {'metadata':{}}
    settings=O.validate_options(dict(factorization='adaptive',mesh_strategy='adaptive'))
    with O.execution_scope(settings), O._AUTOMATIC_REQUEST.override(True), \
         mock.patch('ghost_backend.twod.preparation.prepare_geometry',return_value=(None,None,object(),1.)), \
         mock.patch('ghost_backend.twod.adaptive_geometry.eligible_snapshot',return_value=(False,'reference required')), \
         mock.patch('ghost_backend.execution.selection.select_backend',return_value=dict(selected='compressed',angle_batch_size=8,
             resource_adjustment={'notice':'smaller batches'})), \
         mock.patch('ghost_backend.twod.solver._run_certified_2d_pair_impl',side_effect=solve):
        result=adaptivity._run_certified(None,{},dict(frequencies_ghz=[1.],elevations_deg=[0]),None,
            lambda *args:progress.append(args),initial_coarsening=4)
    assert actual==[8]
    assert result['metadata']['adaptive_mesh']['angle_batch_size']==8
    assert progress[0][-1]=='smaller batches'


@pytest.mark.parametrize('kind',['pec','ibc','dielectric','magnetic','layered','mixed','coated'])
def test_learned_hint_fields_match_dense_across_material_families(kind):
    import os
    from test_experimental_cpu import fixture, fields
    from ghost_backend.twod import solver
    from ghost_backend.execution.options import validate_options
    import ghost_backend.compressed.factor as F
    snapshot=fixture(kind,192)
    options=validate_options(dict(factorization='compressed',mesh_strategy='global',basis_order=1,
        assembly_threads=2,blas_threads=2,ram_budget_gib=8,rhs_compression='off'))
    arguments=dict(geometry_snapshot=snapshot,frequencies_ghz=[.6],elevations_deg=[0.,37.,90.],
        geometry_units='meters',solver_method='experimental_cpu',compute_condition_number=True)
    with mock.patch.dict(os.environ,{'GHOST_HMATRIX_MIN_UNKNOWNS':'100'}):
        reference=solver.solve_monostatic_rcs_2d(**arguments,execution_options=dict(options,factorization='dense'))
        with hints.scope([.6],snapshot,None,'meters'):
            with mock.patch.object(F,'PRECONDITIONER_TOLERANCE',1e-10):
                solver.solve_monostatic_rcs_2d(**arguments,execution_options=options)
            actual=solver.solve_monostatic_rcs_2d(**arguments,execution_options=options)
    factors=actual['metadata']['compressed_factors']
    assert factors and all(f['preconditioner_hint']['accepted'] for f in factors)
    for pol in ('VV','HH'):
        np.testing.assert_allclose(fields(actual,pol),fields(reference,pol),rtol=2e-9,atol=1e-11)


def test_loss_metadata_does_not_discount_the_rank_model():
    from ghost_backend.compressed import memory, hmatrix
    info=SimpleNamespace(k_minus=10-2j,k_plus=1+0j)
    model={'operator_bytes':123,'inverse_rank':77}
    with mock.patch.object(hmatrix,'selected',return_value=True), \
         mock.patch.object(hmatrix,'configuration_unsupported',return_value=None), \
         mock.patch('ghost_backend.compressed.runtime.coordinates',return_value=np.zeros((100,2))), \
         mock.patch.object(hmatrix,'support_radius',return_value=np.ones(100)), \
         mock.patch.object(hmatrix,'forecast_storage',return_value=model) as forecast:
        value=memory.hmatrix_storage(SimpleNamespace(nodes=range(50)),[info],'single_dielectric',100)
    assert value['inverse_rank']==77 and value['operator_bytes']==123
    assert value['medium_wavenumbers'][1]['imag']==-2
    assert not value['attenuation_calibrated']
    assert forecast.call_args.args[2]==abs(10-2j)


def test_candidate_range_is_not_presented_as_final_capacity():
    from ghost_backend.execution.selection import describe_mesh_scope
    result={'meshes':[{'unknowns':100},{'unknowns':150}]}
    describe_mesh_scope(result)
    assert result['mesh_forecast_scope']['initial_candidate_unknowns_min']==100
    assert result['mesh_forecast_scope']['initial_candidate_unknowns_max']==150
    assert not result['mesh_forecast_scope']['final_size_guaranteed']


@pytest.mark.parametrize('kind',['dielectric','layered'])
def test_actual_paired_fallback_publishes_each_polarization(kind):
    import os
    from test_experimental_cpu import fixture
    from ghost_backend.compressed import hmatrix
    from ghost_backend.twod import solver
    from ghost_backend.execution.options import validate_options
    options=validate_options(dict(factorization='compressed',mesh_strategy='global',basis_order=1,
        assembly_threads=2,blas_threads=2,ram_budget_gib=8))
    with mock.patch.dict(os.environ,{'GHOST_HMATRIX_MIN_UNKNOWNS':'100'}), \
         mock.patch.object(hmatrix,'build_pair',side_effect=hmatrix.HMatrixRejected('forced paired rank rejection')) as rejected:
        result=solver.solve_monostatic_rcs_2d(fixture(kind,192),[.6],[0.,37.],geometry_units='meters',
            solver_method='experimental_cpu',execution_options=options)
    assert rejected.call_count>0
    evidence=[f['compressed']['fallback_admission'] for f in result['metadata']['compressed_factors']]
    assert {e['polarization'] for e in evidence}=={'TE','TM'}
    assert all('forced paired rank rejection' in e['reason'] for e in evidence)


def test_regional_pair_storage_rejection_retries_single_hierarchical_operators():
    import os
    from test_experimental_cpu import fixture
    from ghost_backend.compressed import hmatrix
    from ghost_backend.twod import solver
    from ghost_backend.execution.options import validate_options
    options=validate_options(dict(factorization='compressed',mesh_strategy='global',basis_order=1,
        assembly_threads=2,blas_threads=2,ram_budget_gib=8))
    with mock.patch.dict(os.environ,{'GHOST_HMATRIX_MIN_UNKNOWNS':'100'}), \
         mock.patch.object(hmatrix,'build_pair',side_effect=MemoryError('combined storage')):
        result=solver.solve_monostatic_rcs_2d(fixture('layered',192),[.6],[0.,37.],geometry_units='meters',
            solver_method='experimental_cpu',execution_options=options)
    assert all(f['compressed']['operator']=='hmatrix' for f in result['metadata']['compressed_factors'])
