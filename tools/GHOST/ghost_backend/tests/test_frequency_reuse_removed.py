"""Retired profiles migrate safely; each solve owns and releases its inverse."""
import gc
import weakref
from unittest import mock

import numpy as np
import pytest

from ghost_backend.compressed.factor import CompressedFactor
from ghost_backend.compressed.hmatrix import HMatrixOperator
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
from ghost_backend.compressed.operator import StreamedOperator
from ghost_backend.execution.options import DEFAULTS, execution_scope, validate_options
from ghost_backend.twod.preparation import preparation_scope, run_resources
from test_compressed_path import Exact


def test_disabled_saved_profile_migrates_without_mutating_the_record():
    old = dict(DEFAULTS, frequency_preconditioner='off')
    assert validate_options(old) == validate_options({})
    assert old['frequency_preconditioner'] == 'off'
    assert 'frequency_preconditioner' not in DEFAULTS


@pytest.mark.parametrize('value', ['reuse', 'invalid', None, False])
def test_explicit_retired_option_is_rejected_with_migration_guidance(value):
    with pytest.raises(ValueError, match='removed.*Remove frequency_preconditioner'):
        validate_options(dict(frequency_preconditioner=value))


@pytest.mark.parametrize('kind', ['streamed', 'hmatrix'])
def test_successive_factors_are_fresh_and_release_completed_operators(kind):
    n = 96
    xy = np.arange(n, dtype=float)[:, None]
    rng = np.random.default_rng(100)
    a = 3*np.eye(n) + rng.normal(size=(n, 4)) @ rng.normal(size=(4, n)) / n
    a = a.astype(complex) + .01j
    rhs = rng.normal(size=(n, 2)) + 1j*rng.normal(size=(n, 2))
    def make(matrix):
        if kind == 'streamed':
            operator = StreamedOperator(Exact(matrix), xy, tile=32)
            return CompressedFactor(operator, storage_budget_bytes=64*1024**2)
        operator = HMatrixOperator(Exact(matrix), xy, leaf=32)
        return HMatrixFactor(operator, storage_budget_bytes=64*1024**2)
    with execution_scope(validate_options(dict(assembly_threads=2, blas_threads=1))), preparation_scope():
        first = make(a)
        first.solve(rhs)
        references = [weakref.ref(first.a), weakref.ref(first.factor)]
        assert first.event['factorizations'] == 1
        del first
        gc.collect()
        assert all(reference() is None for reference in references)
        assert not run_resources()
        current = a + .005*np.eye(n)
        second = make(current)
        assert second.event['factorizations'] == 1
        assert 'frequency_preconditioner' not in second.event
        for trans, matrix in ((0, current), (1, current.T), (2, current.conj().T)):
            np.testing.assert_allclose(second.inverse(rhs, trans), np.linalg.solve(matrix, rhs),
                                       rtol=2e-11, atol=2e-13)
        assert second.event['max_backward_error'] <= 1e-12
        assert not run_resources()


def test_cancellation_does_not_rebuild_or_retain_inverse():
    with preparation_scope():
        operator = StreamedOperator(Exact(np.eye(16, dtype=complex)),
                                    np.arange(16)[:, None], tile=16)
        factor = CompressedFactor(operator)
        factor.checkpoint = mock.Mock(side_effect=InterruptedError('canceled'))
        with pytest.raises(InterruptedError, match='canceled'):
            factor.solve(np.ones(16))
        assert factor.event['factorizations'] == 1
        assert not run_resources()


def test_retired_factor_arguments_are_not_silently_ignored():
    with pytest.raises(TypeError, match='recycling_key'):
        CompressedFactor(None, recycling_key=b'old-script')
