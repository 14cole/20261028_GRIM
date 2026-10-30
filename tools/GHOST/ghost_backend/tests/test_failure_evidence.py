"""Failure evidence survives refused fallbacks without changing solve policy."""
import json
import pickle
import traceback
from unittest.mock import Mock, patch

import pytest
from ghost_backend.execution import failure, cpu, memory_budget as mb
from ghost_backend.execution.errors import BackendNumericalError
from ghost_backend.execution.options import execution_scope, current_options
from ghost_backend.twod import adaptivity, solver
from test_adaptive_polynomial import wavelength_fixture
from test_request_memory_budget import simulated, GIB


def test_both_adaptive_reasons_survive_reference_memory_refusal():
    original = MemoryError('reference requires 33 GiB')
    original.__cause__ = RuntimeError('original cause')
    def low_level(**kwargs):
        return dict(metadata=dict(panel_count=16, linear_node_count=48))
    def reject(*args):
        raise ValueError('Certified 2-D mesh convergence failed: unresolved field')
    with execution_scope(dict(mesh_strategy='adaptive', factorization='compressed')), \
         patch('ghost_backend.twod.adaptive_geometry.eligible_snapshot', return_value=(True,'')), \
         patch.object(solver, '_finish_certified_2d_pair', side_effect=reject), \
         patch.object(solver, '_run_certified_2d_pair_impl', side_effect=original), \
         patch('ghost_backend.execution.selection.select_backend', side_effect=AssertionError('picker')):
        with pytest.raises(MemoryError) as caught:
            adaptivity.run_certified(low_level, wavelength_fixture(),
                dict(frequencies_ghz=[1.], elevations_deg=[0.], geometry_units='meters'), None, None)
    assert caught.value is original
    assert str(original).startswith('reference requires 33 GiB')
    assert str(original.__cause__) == 'original cause'
    records = original.solver_diagnostics['adaptive_failures']
    assert [r['initial_coarsening'] for r in records] == [8.,4.]
    assert [r['transition'] for r in records] == ['conservative_retry','reference_fallback']
    assert all(len(r['steps']) == 4 and 'unresolved field' in r['reason'] for r in records)
    assert 'coarsening 8' in str(original) and 'coarsening 4' in str(original)
    notes = [v for v in original.__notes__ if v.startswith(failure.NOTE_PREFIX)]
    assert len(notes) == 1
    assert json.loads(notes[0][len(failure.NOTE_PREFIX):]) == original.solver_diagnostics
    restored = pickle.loads(pickle.dumps(original))
    assert restored.solver_diagnostics == original.solver_diagnostics
    assert 'adaptive_failures' in ''.join(traceback.format_exception(original))


def test_ineligible_retry_and_failed_numerical_step_are_recorded():
    for eligible, final_type in (([(True,''),(False,'primitive limit')],MemoryError),
                                 ([(True,''),(True,'')],BackendNumericalError)):
        with execution_scope(dict(mesh_strategy='adaptive', factorization='compressed')), \
             patch('ghost_backend.twod.adaptive_geometry.eligible_snapshot', side_effect=eligible), \
             patch.object(solver, '_run_certified_2d_pair_impl', side_effect=MemoryError('no room')):
            with pytest.raises(final_type) as caught:
                adaptivity.run_certified(Mock(side_effect=BackendNumericalError('bad solve')),
                    wavelength_fixture(), dict(frequencies_ghz=[1.], elevations_deg=[0.],geometry_units='meters'),None,None)
        records = caught.value.solver_diagnostics['adaptive_failures']
        assert records[0]['steps'][0]['status'] == 'failed'
        assert records[0]['steps'][0]['polynomial_degree'] == 2
        assert records[-1]['transition'] == ('ineligible_reference_fallback' if final_type is MemoryError else 'numerical_failure')


@pytest.mark.parametrize('required, fits', [(3.,True),(20.,False)])
def test_dense_guidance_only_forecasts_actual_failed_mesh(required, fits):
    state=cpu.CPUState();state.n_rhs=361
    state.current_resources=dict(nodes=100,system_dofs=200,n_regions=2,operator_matrices=4,
                                 basis_width=4,formulation='single_dielectric')
    error=BackendNumericalError('failed compressed')
    def estimate(n,*args,**kwargs):
        assert n==100 and kwargs['system_dofs']==200 and kwargs['n_rhs']==361
        assert kwargs['dense_resources']['basis_width']==4
        assert current_options()['factorization']=='dense'
        assert not kwargs.get('activate_memory_plan',False)
        return required+1  # includes the old team's allowance, removed for a fresh retry
    with simulated(cap=12.) as (_,ledger), cpu._STATE.override(state), \
         patch.object(solver,'_estimate_memory_gb',side_effect=estimate) as forecast, \
         patch('ghost_backend.compressed.worker_pool.retained_bytes',return_value=GIB), \
         patch('ghost_backend.twod.fields.DenseFactor',side_effect=AssertionError('dense solve')):
        plan={'sentinel':True};ledger.plan=plan
        target=Mock(side_effect=error)
        with pytest.raises(BackendNumericalError) as caught:
            failure.invoke(target,(),{})
        assert caught.value is error and target.call_count==1 and forecast.call_count==1
        assert ledger.plan is plan
        assert current_options()['factorization']=='compressed'
    d=error.solver_diagnostics['dense_override']
    assert d['fits'] is fits and d['peak_gib']==required and not d['automatic_retry']
    assert d['scope']=='failed_mesh_only_after_releasing_failed_solve'
    assert ('Select Dense explicitly' in str(error)) is fits


def test_optional_forecast_failure_preserves_numerical_error():
    state=cpu.CPUState();state.current_resources={'nodes':10,'system_dofs':20}
    error=BackendNumericalError('keep me')
    with execution_scope(dict(factorization='compressed')),cpu._STATE.override(state), \
         patch.object(failure,'dense_advisory',side_effect=RuntimeError('probe failed')):
        with pytest.raises(BackendNumericalError) as caught:
            failure.invoke(Mock(side_effect=error),(),{})
    assert caught.value is error and str(error)=='keep me'
    assert error.solver_diagnostics['dense_override']['status']=='unavailable'


@pytest.mark.parametrize('exc',[MemoryError('budget'),InterruptedError('cancel'),ValueError('input')])
def test_other_failures_do_not_trigger_dense_guidance(exc):
    with patch.object(failure,'dense_advisory',side_effect=AssertionError('unexpected')):
        with pytest.raises(type(exc)) as caught:failure.invoke(Mock(side_effect=exc),(),{})
    assert caught.value is exc and not hasattr(exc,'solver_diagnostics')


def test_real_public_failure_gets_guidance_without_dense_retry():
    with patch('ghost_backend.compressed.factor.CompressedFactor.solve',side_effect=BackendNumericalError('injected')), \
         patch('ghost_backend.twod.fields.DenseFactor',side_effect=AssertionError('dense retry')):
        with pytest.raises(BackendNumericalError) as caught:
            solver.solve_monostatic_rcs_2d(wavelength_fixture(),[1.],[0.],geometry_units='meters')
    d=caught.value.solver_diagnostics['dense_override']
    assert d['status']=='estimated' and d['system_dofs']>0 and not d['automatic_retry']
    assert current_options() is None


def test_dense_forecast_does_not_inherit_temporary_compressed_batch_shrink():
    from ghost_backend.execution import angle_batch
    state=cpu.CPUState();state.n_rhs=361
    state.current_resources=dict(nodes=100,system_dofs=200,n_regions=1,basis_width=4)
    def estimate(*args,**kwargs):
        assert cpu.configured_batch_size()==256
        return 3.
    with simulated(cap=12.),angle_batch.scope(),patch.object(solver,'_estimate_memory_gb',side_effect=estimate), \
         patch('ghost_backend.compressed.worker_pool.retained_bytes',return_value=0):
        angle_batch._RECOVERY.get()['limit']=1
        result=failure.dense_advisory(state)
        assert result['angle_batch_size']==256
        assert angle_batch.limit()==1


def test_dense_advisory_preserves_environment_only_launch_settings(monkeypatch):
    monkeypatch.setenv('GHOST_CPU_ANGLE_BATCH_SIZE','64')
    monkeypatch.setenv('GHOST_MAX_SOLVE_GB','7')
    monkeypatch.setenv('GHOST_CPU_FACTORIZATION','compressed')
    state=cpu.CPUState();state.current_resources=dict(nodes=100,system_dofs=200)
    def estimate(*args,**kwargs):
        assert cpu.configured_batch_size()==64
        assert current_options()['ram_budget_gib']==7.
        return 3.
    assert current_options() is None
    with patch.object(solver,'_estimate_memory_gb',side_effect=estimate), \
         patch.object(solver,'_solve_memory_limit_gb',return_value=7.), \
         patch('ghost_backend.compressed.worker_pool.retained_bytes',return_value=0):
        result=failure.dense_advisory(state)
    assert result['angle_batch_size']==64 and result['fits']
    assert current_options() is None
