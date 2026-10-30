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
