"""Percentiles select observed samples by default and optionally interpolate."""
import json
import warnings

import numpy as np
import pytest

from GRIM_Backend.datasets import reduction_workspace as reduction
from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.result_storage import operation_result_storage


def _grid(dtype=np.float64):
    lanes = np.asarray([
        [0., 10., 20., 30., 40., np.nan],
        [5., np.nan, 5., 5., 9., np.nan],
        [np.nan] * 6,
        [np.nan, np.nan, 7., np.nan, np.nan, np.nan],
    ], dtype=dtype)
    return RcsGrid(
        np.arange(6.), [0.], [1., 2.], ["HH", "VV"],
        rcs_power=lanes.T.reshape(6, 1, 2, 2), units={"frequency": "GHz"},
    )


@pytest.mark.parametrize("streamed", [False, True])
@pytest.mark.parametrize("dtype", [np.float32, np.float64])
@pytest.mark.parametrize("axes", [(0,), (0, 2, 3)])
@pytest.mark.parametrize("percentile", [0., 1., 40., 50., 73.5, 100.])
@pytest.mark.parametrize("interpolate", [None, True, False])
def test_percentile_modes_match_numpy(tmp_path, monkeypatch, streamed, dtype, axes, percentile, interpolate):
    source = _grid(dtype)
    if streamed:
        monkeypatch.setattr(reduction, "BLOCK_CELLS", 3)
        workspace_array = reduction.workspace_array
        monkeypatch.setattr(reduction, "workspace_array", lambda shape, dtype: workspace_array(shape, dtype, ram_limit_bytes=0))
    with warnings.catch_warnings(), operation_result_storage("disk" if streamed else "memory", cache_dir=tmp_path):
        warnings.simplefilter("ignore", RuntimeWarning)
        expected = np.nanpercentile(
            source.power, percentile, axis=axes, keepdims=True,
            method="linear" if interpolate else "inverted_cdf",
        )
        kwargs = {} if interpolate is None else {"interpolate": interpolate}
        actual = reduction.reduce_dataset(source, "magnitude", axes, "percentile", percentile, **kwargs)
    assert actual.dtype == expected.dtype
    np.testing.assert_allclose(actual, expected, rtol=8 * np.finfo(expected.dtype).eps, atol=0., equal_nan=True)


def test_dataset_alias_broadcast_and_interpolation_metadata():
    source = RcsGrid([0., 1., 2., 3.], [0.], [1.], ["HH"],
                     rcs_power=np.asarray([0., 10., 20., 30.]).reshape(4, 1, 1, 1))
    default = source.statistics_dataset("p50", axes=("azimuth",))
    interpolated = source.statistics_dataset("percentile", axes=("azimuth",), percentile=50.,
                                             interpolate=True, broadcast_reduced=True)
    assert default.power.item() == 10.
    np.testing.assert_array_equal(interpolated.power, np.full(source.shape, 15.))
    assert json.loads(default.extra["statistics_reduction_json"])["interpolate"] is False
    assert json.loads(interpolated.extra["statistics_reduction_json"])["interpolate"] is True


@pytest.mark.parametrize("statistic", ["mean", "median", "min", "max", "std"])
def test_interpolation_setting_does_not_change_other_statistics(statistic):
    source = _grid()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        default = source.statistics_dataset(statistic, axes=("azimuth",))
        enabled = source.statistics_dataset(statistic, axes=("azimuth",), interpolate=True)
    np.testing.assert_array_equal(default.power, enabled.power)
    assert json.loads(enabled.extra["statistics_reduction_json"])["interpolate"] is None


@pytest.mark.parametrize("streamed", [False, True])
def test_median_remains_conventional_with_interpolation_disabled(monkeypatch, streamed):
    if streamed:
        monkeypatch.setattr(reduction, "BLOCK_CELLS", 3)
    source = RcsGrid([0., 1., 2., 3.], [0.], [1.], ["HH"],
                     rcs_power=np.asarray([0., 10., 20., 30.]).reshape(4, 1, 1, 1))
    assert source.statistics_dataset("median", axes=("azimuth",)).power.item() == 15.
    assert source.statistics_dataset("p50", axes=("azimuth",)).power.item() == 10.


def test_rank_helpers_default_to_observed_percentile():
    values = np.asarray([0., 10., 20., 30.])
    assert reduction._exact_rank((values,), values.size, values.dtype, "percentile", 50.) == 10.
    result = reduction._vectorized_nan_rank(values, (0,), np.percentile, (50.,))
    assert result.item() == 10.


@pytest.mark.parametrize("percentile", [-1., 101., np.nan])
@pytest.mark.parametrize("streamed", [False, True])
def test_noninterpolated_percentile_rejects_invalid_probability(monkeypatch, percentile, streamed):
    if streamed:
        monkeypatch.setattr(reduction, "BLOCK_CELLS", 3)
    with pytest.raises(ValueError, match="Percentiles must be in the range"):
        reduction.reduce_dataset(_grid(), "magnitude", (0,), "percentile", percentile, interpolate=False)
