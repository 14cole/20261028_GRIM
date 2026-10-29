"""Ordinary 2D runs keep the selected backend throughout certification."""
from contextlib import ExitStack
from unittest.mock import patch

import numpy as np
import pytest

from ghost_backend.execution.options import current_options
from ghost_backend.execution.errors import BackendNumericalError
from ghost_backend.twod import solver
from test_adaptive_polynomial import wavelength_fixture
from test_experimental_cpu import fields


@pytest.mark.parametrize('mode', [None, 'dense'])
def test_certification_refines_without_backend_picker_or_history(mode):
    with ExitStack() as stack:
        stack.enter_context(patch('ghost_backend.twod.adaptive_geometry.MIN_AUTOMATIC_REFERENCE_PANELS', 0))
        for target in ('execution.selection.select_backend', 'execution.timing_history.read',
                       'execution.timing_history.record', 'execution.timing_history.adjust'):
            stack.enter_context(patch('ghost_backend.' + target, side_effect=AssertionError(target)))
        kwargs = {} if mode is None else {'execution_options': {'factorization': mode}}
        result = solver.solve_monostatic_rcs_2d_certified(wavelength_fixture(), [1.], [0., 47., 91.],
            geometry_units='meters', **kwargs)
    metadata = result['metadata']
    assert metadata['mesh_convergence_certified']
    assert metadata['adaptive_mesh']['used']
    assert metadata['polynomial_degree'] == 3
    assert metadata['execution_options']['factorization'] == (mode or 'compressed')
    assert all(step['backend'] == (mode or 'compressed') and step['backend_selection'] is None
               for step in metadata['adaptive_mesh']['steps'])
    assert 'backend_selection' not in metadata
    assert current_options() is None
    reference = solver.solve_monostatic_rcs_2d_certified(wavelength_fixture(), [1.], [0., 47., 91.],
        geometry_units='meters', solver_method='direct',
        execution_options=dict(factorization='dense', mesh_strategy='global'))
    for pol in ('VV', 'HH'):
        a, b = fields(result, pol), fields(reference, pol)
        assert np.max(abs(a-b))/np.max(abs(b)) < .002


@pytest.mark.parametrize('failure', [MemoryError, BackendNumericalError])
def test_default_compressed_failure_does_not_silently_allocate_dense(failure):
    with patch('ghost_backend.compressed.factor.CompressedFactor.solve', side_effect=failure('injected')), \
         patch('ghost_backend.linalg.dense.DenseFactor', side_effect=AssertionError('dense retry')):
        with pytest.raises(failure, match='injected'):
            solver.solve_monostatic_rcs_2d(wavelength_fixture(), [1.], [0.], geometry_units='meters')
    assert current_options() is None


def test_launch_dense_override_and_partial_profile_default(monkeypatch):
    monkeypatch.setenv('GHOST_CPU_FACTORIZATION', 'dense')
    args = (wavelength_fixture(), [1.], [0.])
    dense = solver.solve_monostatic_rcs_2d(*args, geometry_units='meters')
    assert dense['metadata']['execution_options']['factorization'] == 'dense'
    monkeypatch.delenv('GHOST_CPU_FACTORIZATION')
    compressed = solver.solve_monostatic_rcs_2d(*args, geometry_units='meters',
        execution_options=dict(angle_batch_size=1))
    assert compressed['metadata']['execution_options']['factorization'] == 'compressed'
    for pol in ('VV', 'HH'):
        np.testing.assert_allclose(fields(dense, pol), fields(compressed, pol), rtol=1e-9, atol=1e-12)


def test_mixed_precision_preserves_supported_default_and_rejects_explicit_compressed(monkeypatch):
    from ghost_backend.linalg.refined_lu import linear_precision
    monkeypatch.delenv('GHOST_CPU_FACTORIZATION', raising=False)
    args = (wavelength_fixture(), [1.], [0.])
    with linear_precision('mixed'):
        result = solver.solve_monostatic_rcs_2d(*args, geometry_units='meters')
        assert result['metadata']['execution_options']['factorization'] == 'dense'
        with pytest.raises(ValueError, match='double precision'):
            solver.solve_monostatic_rcs_2d(*args, geometry_units='meters',
                execution_options=dict(factorization='compressed'))
        monkeypatch.setenv('GHOST_CPU_FACTORIZATION', 'compressed')
        with pytest.raises(ValueError, match='double precision'):
            solver.solve_monostatic_rcs_2d(*args, geometry_units='meters')
