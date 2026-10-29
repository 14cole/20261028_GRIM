"""Selection evidence must describe policy overrides and live admission."""
import copy
import time
from unittest.mock import patch
import pytest

from ghost_backend.execution.policy import rank_candidates, ranking_reason
from ghost_backend.execution import timing_history
from ghost_backend.execution.options import validate_options
from ghost_backend.execution.selection import select_backend, _refresh_memory_forecast
from ghost_backend.twod import solver
from ghost_backend.tests.general_fixtures import fixture


def candidates():
    return dict(dense=dict(cost=100.,peak_gb=4.),
                compressed=dict(cost=1.,peak_gb=2.,hmatrix=True))


def test_dense_preference_is_reported_without_relabeling_cost_winner():
    evidence={}
    original=candidates()
    assert rank_candidates(original,8,diagnostics=evidence)==['dense','compressed']
    assert evidence['cost_winner']=='compressed' and evidence['selected']=='dense'
    assert evidence['preference_changed_winner'] and 'Dense-first' in ranking_reason(evidence)
    assert original==candidates()


def test_admission_explains_margin_exclusion_and_full_budget_fallback():
    evidence={}
    assert rank_candidates(candidates(),4,diagnostics=evidence)==['compressed']
    assert evidence['excluded']=={'dense':'outside_memory_margin'}
    assert not evidence['dense_preference_applied'] and evidence['margin_applied']
    assert rank_candidates(candidates(),2,diagnostics=evidence)==['compressed']
    assert evidence['excluded']=={'dense':'exceeds_budget'}
    assert not evidence['margin_applied']


def test_measured_costs_report_dense_override_and_preserve_input():
    initial=dict(selected='dense',admission_budget_gib=8,candidates=candidates())
    before=copy.deepcopy(initial);stamp=time.time()-1
    revised=timing_history.adjust(initial,'test',entries={'test':{
        'dense':[[stamp,100.],[stamp,100.]],'compressed':[[stamp,1.],[stamp,1.]]}})
    assert revised['selected']=='dense'
    assert revised['ranking']['cost_winner']=='compressed'
    assert revised['ranking']['preference_changed_winner']
    assert revised['cost_source']=='exact_request_repeated_timings'
    assert 'Dense-first' in revised['reason'] and initial==before


def test_forecast_refresh_replaces_stale_ranking_and_reports_mesh_scope():
    request=dict(geometry_snapshot=fixture('rectangle',24),frequencies_ghz=[1.],
                 elevations_deg=[0.,90.],geometry_units='meters')
    options=validate_options(dict(factorization='adaptive',ram_budget_gib=8))
    with patch.object(solver,'_solve_memory_limit_gb',return_value=8):
        forecast=select_backend(request,options,certified=True)
    assert forecast['cost_scope']['systems']==len(forecast['meshes'])
    assert forecast['ranking']['selected']==forecast['selected']
    resources=[(r['resources'],dict(options,basis_order=r['polynomial_degree'])) for r in forecast['meshes']]
    forecast['candidates']['compressed']['hmatrix']=True
    with patch.object(solver,'_solve_memory_limit_gb',return_value=4), \
         patch.object(solver,'_estimate_memory_gb',return_value=3.5):
        _refresh_memory_forecast(forecast,resources,request,options)
    assert forecast['ranking']['budget_gib']==4
    assert not forecast['ranking']['margin_applied']
    assert 'Lowest predicted cost' not in forecast['reason']


def test_reused_adaptive_steps_keep_aggregate_scope_and_policy_evidence():
    from ghost_backend.tests.test_adaptive_polynomial import wavelength_fixture
    with patch('ghost_backend.twod.adaptive_geometry.MIN_AUTOMATIC_REFERENCE_PANELS',0):
        result=solver.solve_monostatic_rcs_2d_certified(wavelength_fixture(),[1.],[0.,90.],
            geometry_units='meters',execution_options=dict(mesh_strategy='adaptive',factorization='adaptive'))
    for step in result['metadata']['adaptive_mesh']['steps'][:2]:
        selection=step['backend_selection']
        assert selection['forecast_reused']
        assert selection['cost_scope']['polynomial_degrees']==[2,3]
        assert selection['selection_override']['selected']==step['backend']
        assert selection['ranking']['cost_winner'] in ('dense','compressed')
        assert 'Underlying forecast:' in selection['reason']


@pytest.mark.parametrize('scenario',['qualified','few','noisy','different_reservation','excluded','batch_limit'])
def test_only_qualified_timing_can_override_dense_within_reservation(tmp_path,monkeypatch,scenario):
    from ghost_backend.tests.test_nearby_timing_history import key,choice,train
    monkeypatch.setenv('GHOST_TIMING_CACHE_DIR',str(tmp_path))
    values=(4.,4.) if scenario=='few' else (2.,4.,6.) if scenario=='noisy' else (4.,4.1,3.9)
    train(key('same'),compressed=values)
    initial=choice();initial['candidates']['compressed']['hmatrix']=True
    request=key('same',family='changed-reservation') if scenario=='different_reservation' else key('same')
    if scenario=='excluded':initial['candidates']['compressed']['peak_gb']=9.
    if scenario=='batch_limit':initial['candidates']['compressed']['peak_gb']=5.
    before=copy.deepcopy(initial)
    revised=timing_history.adjust(initial,request,batch=scenario=='batch_limit')
    assert revised['selected']==('compressed' if scenario=='qualified' else 'dense')
    assert initial==before
    assert revised['candidates']['compressed']['peak_gb']==initial['candidates']['compressed']['peak_gb']
    if scenario=='qualified':
        assert revised['qualified_timing_preference']
        assert not revised['ranking']['dense_preference_enabled']
        assert 'Stable paired timing evidence' in revised['reason']
    elif scenario in ('few','noisy','different_reservation'):
        assert not revised['qualified_timing_preference']
    else:
        assert revised['ranking']['excluded']['compressed']=='exceeds_budget'


def test_qualified_stage_evidence_also_replaces_dense_preference(tmp_path,monkeypatch):
    from ghost_backend.tests.test_stage_cost_model import train,request,selection
    monkeypatch.setenv('GHOST_TIMING_CACHE_DIR',str(tmp_path))
    train('dense',request('dense',10.),scale=1.)
    train('compressed',request('compressed',10.1),scale=.35)
    initial=selection(1050);initial['candidates']['compressed']['hmatrix']=True
    revised=timing_history.adjust(initial,request('target',10.5))
    assert revised['selected']=='compressed' and revised['qualified_timing_preference']
    assert revised['cost_source']=='matched_solver_stages'
