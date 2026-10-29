"""The Statistics RAM estimate follows the streaming reducer, not full-source copies."""
import math

import numpy as np

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.reduction_workspace import BLOCK_CELLS, RAM_WORKSPACE_BYTES
from GRIM_Backend.ui.dataset_actions import _statistics_peak_estimate


def _dataset(shape):
    axes = [np.arange(n, dtype=float) for n in shape[:3]]
    return RcsGrid(axes[0], axes[1], axes[2], [f"P{i}" for i in range(shape[3])],
                   rcs_power=np.ones(shape), rcs_phase=np.zeros(shape))


def test_large_population_estimate_is_bounded_scratch_plus_outputs():
    dataset = _dataset((2000, 1, 500, 1))
    source_bytes = 2000 * 500 * 8
    for statistic in ("mean", "median", "percentile", "std", "min"):
        estimate = _statistics_peak_estimate(
            [dataset], statistic=statistic, reduce_indices={0}, broadcast_reduced=False)
        outputs = 500 * 8 * 2
        rank = min(2000 * 8, RAM_WORKSPACE_BYTES) if statistic in {"median", "percentile"} else 0
        assert estimate == outputs + BLOCK_CELLS * 8 * 4 + rank
        assert estimate < source_bytes
    # A complete reduction keeps the rank workspace at the RAM cap: larger
    # populations partition on disk scratch instead of in RAM.
    complete = _statistics_peak_estimate(
        [dataset], statistic="median", reduce_indices={0, 1, 2, 3}, broadcast_reduced=False)
    assert complete == 8 * 2 + BLOCK_CELLS * 8 * 4 + min(1_000_000 * 8, RAM_WORKSPACE_BYTES)


def test_small_dataset_and_broadcast_charge_only_what_is_allocated():
    dataset = _dataset((4, 1, 3, 2))
    cells = 4 * 3 * 2
    plain = _statistics_peak_estimate(
        [dataset], statistic="mean", reduce_indices={2}, broadcast_reduced=False)
    assert plain == (4 * 2) * 8 * 2 + cells * 8 * 4
    broadcast = _statistics_peak_estimate(
        [dataset, dataset], statistic="max", reduce_indices={2}, broadcast_reduced=True)
    assert broadcast == 2 * cells * 8 * 2 + cells * 8 * 4 + (4 * 2) * 8
    assert math.prod(dataset.power.shape) == cells
