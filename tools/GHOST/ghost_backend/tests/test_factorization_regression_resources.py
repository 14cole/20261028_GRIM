"""Residency across mesh transitions and atomic storage-cap rejection."""
from unittest import mock

import numpy as np
import pytest

from ghost_backend.compressed import memory
from ghost_backend.compressed.operator import StreamedOperator


def test_hmatrix_forecast_keeps_previous_mesh_workers_and_polynomial_storage():
    model = dict(operator_bytes=100000, inverse_bytes=50000, inverse_peak_bytes=70000,
                 assembly_workspace_bytes=20000, method='test', coefficients=1000, inverse_rank=20)
    with mock.patch('ghost_backend.compressed.runtime.hmatrix_storage_budget', return_value=2**30), \
            mock.patch('ghost_backend.compressed.worker_pool.retained_bytes', return_value=0) as workers, \
            mock.patch('ghost_backend.twod.assembly.polynomial_pair.retained_bytes', return_value=0) as polynomial:
        first = memory.hmatrix_forecast(100, 200, 361, 256, 4, {}, model)
        workers.return_value = 512 * memory.MIB
        polynomial.return_value = 64 * memory.MIB
        second = memory.hmatrix_forecast(100, 200, 361, 256, 4, {}, model)
    added = 576 * memory.MIB
    assert second['peak_bytes'] - first['peak_bytes'] == added
    assert all(second['phase_bytes'][phase] - value == added
               for phase, value in first['phase_bytes'].items())
    assert second['retained_worker_allowance_bytes'] == 512 * memory.MIB
    assert second['retained_polynomial_operator_bytes'] == 64 * memory.MIB
    assert second['storage_limit_bytes'] == first['storage_limit_bytes']
    assert second['resident_operator_bytes'] == first['resident_operator_bytes']


def test_storage_refusal_preserves_operator_and_reports_required_bytes():
    class Oracle:
        n = 16
    operator = StreamedOperator(Oracle(), np.arange(16)[:, None], tile=16,
                                budget=2**20, assemble=False)
    raw = np.eye(16, dtype=complex)
    tile = operator.compress_tile(0, 0, raw, np.zeros(raw.shape))
    before = operator.bytes
    required = before + raw.nbytes
    operator.budget = required - 1
    with pytest.raises(MemoryError, match=f'{required} bytes required, {required - 1} bytes allowed'):
        operator.store_tile(tile)
    assert operator.bytes == before and not operator.tiles
    assert not np.any(operator.row_norm) and not np.any(operator.column_norm)
    assert operator.peak_tile == 0 and operator.compressed == 0
    operator.budget = required
    operator.store_tile(tile)
    assert operator.bytes == required
    np.testing.assert_array_equal(operator.row_norm, np.ones(16))
    np.testing.assert_array_equal(operator.tiles[0, 0][0], raw)
