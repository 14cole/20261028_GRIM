"""Sweep percentile method survives controls, plotting, Hold, and replay."""
import os
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.plotting import sweep_analysis as sweep
from GRIM_Backend.plotting.modes import elevation_sweep_mode, frequency_mode
from GRIM_Backend.scripting.plotting import plot_datasets
from GRIM_Backend.ui.analysis_controls import PlotAnalysisControls
from test_plot_renderer_correctness import _RendererHarness


@pytest.fixture
def controls():
    app = QApplication.instance() or QApplication([])
    result = PlotAnalysisControls()
    yield result
    result.cdf_dialog.close()
    result.cdf_dialog.deleteLater()
    result.deleteLater()
    app.processEvents()


def _grid(storage="power"):
    power = np.broadcast_to(np.array([0., 1., 3., 100.])[:, None, None, None], (4, 2, 2, 1)).copy()
    if storage == "complex":
        # Varying phase must not change magnitude scores.
        samples = {"rcs": np.sqrt(power) * np.exp(1j * np.arange(4)[:, None, None, None])}
    else:
        samples = {"rcs_power": power}
    return RcsGrid([0., 10., 20., 30.], [0., 10.], [9., 10.], ["HH"],
                   units={"azimuth": "deg", "elevation": "deg", "frequency": "GHz"}, **samples)


def _owner(dataset, controls):
    result = _RendererHarness([("RCS", dataset)], selections={
        "azimuth": dataset.azimuths, "elevation": dataset.elevations,
        "frequency": dataset.frequencies, "polarization": ["HH"],
    })
    result.analysis_controls = controls
    return result


@pytest.mark.parametrize("interpolate", [True, False])
@pytest.mark.parametrize("percentile,linear,rank", [(0., 0., 0.), (50., 2., 1.), (90., 70.9, 100.), (100., 100., 100.)])
def test_sweep_percentile_uses_valid_power_population(interpolate, percentile, linear, rank):
    values = np.array([[0., np.nan], [1., -1.], [3., np.inf], [100., np.nan],
                       [np.nan, np.nan], [-4., np.nan], [np.inf, np.nan]])
    config = sweep.options({"mode": "percentile", "percentile": percentile, "interpolate": interpolate})
    actual, counts = sweep.reduce_power(values, config)
    assert actual[0] == pytest.approx(linear if interpolate else rank)
    assert np.isnan(actual[1])
    np.testing.assert_array_equal(counts, [4, 0])


@pytest.mark.parametrize("mode,expected", [("mean", 50.5), ("median", 50.5), ("max", 100.)])
def test_percentile_toggle_does_not_change_other_statistics(mode, expected):
    for interpolate in (True, False):
        actual, _ = sweep.reduce_power([[1.], [100.]], sweep.options({"mode": mode, "interpolate": interpolate}))
        assert actual[0] == expected


def test_sweep_checkbox_defaults_enabled_state_signals_and_saved_options(controls):
    assert not controls.chk_sweep_interpolate.isChecked()
    assert not controls.sector_interpolate()
    assert not controls.chk_sweep_interpolate.isEnabled()
    seen = []
    controls.changed.connect(seen.append)
    controls.combo_sweep_aggregation.setCurrentIndex(controls.combo_sweep_aggregation.findData("percentile"))
    assert controls.chk_sweep_interpolate.isEnabled()
    controls.chk_sweep_interpolate.setChecked(True)
    assert seen == ["sweep", "sweep"]
    saved = controls.analysis_options()
    assert saved["sweep"] == {"mode": "percentile", "percentile": 90., "interpolate": True}
    controls.combo_sweep_aggregation.setCurrentIndex(controls.combo_sweep_aggregation.findData("median"))
    assert not controls.chk_sweep_interpolate.isEnabled()
    seen.clear()
    controls.restore_analysis_options(saved)
    assert not seen
    assert controls.analysis_options() == saved
    assert controls.chk_sweep_interpolate.isEnabled()
    # Missing method in an older session or script follows the nearest-rank default.
    legacy = {"mode": "percentile", "percentile": 90.}
    controls.restore_analysis_options({"sweep": legacy})
    assert not controls.chk_sweep_interpolate.isChecked()
    assert sweep.options(legacy)["interpolate"] is False
    controls.chk_sweep_interpolate.setChecked(True)
    controls.restore_analysis_options({"sweep": dict(legacy, interpolate=False)})
    assert not controls.chk_sweep_interpolate.isChecked()


@pytest.mark.parametrize("mode,renderer", [("frequency", frequency_mode), ("elevation_sweep", elevation_sweep_mode)])
def test_missing_interpolation_option_uses_nearest_rank_everywhere(controls, mode, renderer):
    dataset = _grid()
    config = {"mode": "percentile", "percentile": 90.}
    actual, _ = sweep.reduce_power([[0.], [1.], [3.], [100.]], config)
    assert actual[0] == 100.
    assert "nearest rank" in sweep.statistic_name(config)
    assert "nearest rank" in sweep.short_statistic(config)
    assert sweep.options()["interpolate"] is False
    controls.restore_analysis_options({"sweep": config})
    harness = _owner(dataset, controls)
    renderer.render(harness)
    figure = plot_datasets([("RCS", dataset)], mode=mode, azimuths=dataset.azimuths,
                           elevations=dataset.elevations, frequencies=dataset.frequencies,
                           polarization="HH", sweep_options=config)
    try:
        for axis in (harness.plot_ax, figure.axes[0]):
            assert len(axis.lines) == 2
            for line in axis.lines:
                np.testing.assert_allclose(line.get_ydata(), 20.)
    finally:
        figure.clear()


@pytest.mark.parametrize("mode,renderer", [("frequency", frequency_mode), ("elevation_sweep", elevation_sweep_mode)])
@pytest.mark.parametrize("storage", ["power", "complex"])
@pytest.mark.parametrize("interpolate,expected", [(True, 70.9), (False, 100.)])
def test_interactive_sweep_and_recorded_headless_replay_agree(controls, mode, renderer, storage, interpolate, expected):
    dataset = _grid(storage)
    config = {"mode": "percentile", "percentile": 90., "interpolate": interpolate}
    controls.restore_analysis_options({"sweep": config})
    harness = _owner(dataset, controls)
    renderer.render(harness)
    assert len(harness.plot_ax.lines) == 2
    for line in harness.plot_ax.lines:
        np.testing.assert_allclose(line.get_ydata(), 10. * np.log10(expected))
        assert ("nearest rank" in line.get_label()) is (not interpolate)
    harness.python_recorder = mock.Mock()
    harness._python_reference_for_dataset = lambda dataset: "dataset"
    harness._record_python_plot(mode)
    recorded = harness.python_recorder.record_plot.call_args.kwargs
    assert recorded["parameters"]["sweep_options"] == config
    figure = plot_datasets([("RCS", dataset)], mode=recorded["mode"], **recorded["parameters"])
    try:
        for interactive, replay in zip(harness.plot_ax.lines, figure.axes[0].lines):
            np.testing.assert_allclose(interactive.get_ydata(), replay.get_ydata())
    finally:
        figure.clear()


def test_hold_keeps_interpolated_and_nearest_rank_scores_distinct(controls):
    dataset = _grid()
    controls.restore_analysis_options({"sweep": {"mode": "percentile", "percentile": 90., "interpolate": True}})
    harness = _owner(dataset, controls)
    frequency_mode.render(harness)
    harness.btn_hold.checked = True
    controls.chk_sweep_interpolate.setChecked(False)
    frequency_mode.render(harness)
    assert len(harness.plot_ax.lines) == 4
    np.testing.assert_allclose(harness.plot_ax.lines[0].get_ydata(), 10. * np.log10(70.9))
    np.testing.assert_allclose(harness.plot_ax.lines[-1].get_ydata(), 20.)


def test_phase_percentile_always_selects_nearest_rank_observation():
    field = np.array([[1.], [2.j], [-3.]])
    for interpolate in (True, False):
        config = sweep.options({"mode": "percentile", "percentile": 50., "interpolate": interpolate})
        actual, counts = sweep.reduce_phase(field, config)
        assert actual[0] == pytest.approx(90.)
        assert counts[0] == 3
        assert "nearest-rank power sample" in sweep.statistic_name(config, phase=True)
