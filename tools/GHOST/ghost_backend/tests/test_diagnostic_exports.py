"""A metadata-only reader must not certify an intentionally relaxed audit."""
from copy import deepcopy
from unittest.mock import patch
import pytest
from ghost_backend.execution.diagnostics import diagnostic_scope, mark_uncertified
from ghost_backend.execution import timing_history


def example():
    return dict(quality_gate=dict(passed=True, channels={'VV':dict(passed=True)}),
        mesh_convergence_certified=True,
        mesh_convergence=dict(passed=True, base_quality_gate=dict(passed=True), delta=.0001),
        channel_metadata={'VV':dict(quality_gate=dict(passed=True), mesh_convergence_certified=True)},
        frequency_metadata=[dict(metadata=dict(quality_gate=dict(passed=True), mesh_convergence_certified=True))])


def test_diagnostic_derivative_clears_nested_certification_and_preserves_measurements():
    source = example()
    before = deepcopy(source)
    result = mark_uncertified(source, dict(condition_est_max=1e99))
    assert source == before
    def check(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('passed', 'mesh_convergence_certified'):
                    assert child is False
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
    check(result)
    assert result['diagnostic_only'] and result['uncertified']
    assert result['quality_gate']['diagnostic_passed']
    assert result['mesh_convergence']['diagnostic_passed']
    assert result['mesh_convergence']['delta'] == .0001
    assert mark_uncertified(result, dict(condition_est_max=1e99)) == result
    with pytest.raises(ValueError):
        mark_uncertified(source, {})


def test_diagnostic_scope_prevents_history_before_export_and_restores():
    with patch.object(timing_history, 'cache_path', side_effect=AssertionError('history opened')):
        with diagnostic_scope(dict(condition_est_max=1e99)):
            with diagnostic_scope({}):
                timing_history.record('key', 'compressed', 1., example())
        normalized = mark_uncertified(example(), dict(condition_est_max=1e99))
        timing_history.record('key', 'compressed', 1., normalized)
        assert not timing_history._clean_success(dict(quality_gate=dict(passed=True),
            channel_metadata={'VV':normalized}), 'compressed')
    from ghost_backend.execution.diagnostics import active
    assert not active()
    assert timing_history._clean_success(example(), 'compressed')


@pytest.mark.parametrize('diagnostic', [False, True])
def test_audit_worker_exports_diagnostic_flags_before_writing(tmp_path, monkeypatch, diagnostic):
    import importlib.util
    import json
    from pathlib import Path
    from ghost_backend.execution.diagnostics import active
    from ghost_backend.twod import solver
    path = Path(__file__).resolve().parents[1]/'Codex_audit/automatic_selection_20261029/study.py'
    spec = importlib.util.spec_from_file_location('diagnostic_export_study', path)
    study = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(study)
    monkeypatch.setattr(study, 'geometry', lambda *args: {})
    # The offline worker patches this gate in its isolated process. Restore it
    # after exercising that worker in the test process.
    monkeypatch.setattr(solver, 'evaluate_quality_gate', solver.evaluate_quality_gate)
    raw = example()
    raw['execution_options'] = dict(factorization='compressed')
    def solve(**kwargs):
        assert active() == diagnostic
        if diagnostic:
            timing_history.record('key', 'compressed', 1., raw)
        return dict(metadata=raw, co_solved_samples={p:[dict(rcs_amp_real=1., rcs_amp_imag=0.)]
                    for p in ('VV', 'HH')})
    monkeypatch.setattr(solver, 'solve_monostatic_rcs_2d_certified', solve)
    with patch('ghost_backend.execution.selection.select_backend', return_value={}), \
         patch.object(timing_history, 'cache_path', side_effect=AssertionError('diagnostic history')):
        study.worker(dict(geometry='fixture', mode='compressed', frequency=1., diagnose_condition=diagnostic), tmp_path)
    metadata = json.loads((tmp_path/'metadata.json').read_text())
    result = json.loads((tmp_path/'result.json').read_text())
    assert metadata['quality_gate']['passed'] == (not diagnostic)
    assert metadata['mesh_convergence_certified'] == (not diagnostic)
    assert result['quality_passed'] == (not diagnostic)
    assert result['mesh_certified'] == (not diagnostic)
    assert result['status'] == ('diagnostic' if diagnostic else 'passed')
    assert raw['quality_gate']['passed'] and raw['mesh_convergence_certified']
    assert not active()
