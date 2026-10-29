"""Waterfall dataset cuts use comparable value scales across separate panels."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from PySide6.QtWidgets import QApplication

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.plotting.image_display import update_waterfall_display
from GRIM_Backend.plotting.modes import waterfall_mode
from GRIM_Backend.ui.image_analysis import ImageAnalysisControls
from test_plot_renderer_correctness import _RendererHarness


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def rendered(app):
    owners = []

    def create(*, horizontal=True, vertical=True, colorbar="off"):
        datasets = []
        for name, values in (
            ("Weak", [[1., 2., 3.], [4., 5., 6.], [7., 8., 9.]]),
            ("Strong", [[10., 12., 14.], [16., 1000., 18.], [20., 22., 24.]]),
        ):
            power = np.asarray(values).T[:, None, :, None]
            datasets.append((name, RcsGrid(
                [0., 1., 2.], [0.], [8., 9., 10.], ["HH"], rcs_power=power,
                units={"azimuth": "deg", "elevation": "deg", "frequency": "GHz",
                       "rcs_linear_quantity": "sigma_3d", "rcs_log_unit": "dBsm"})))
        dataset = datasets[0][1]
        owner = _RendererHarness(datasets, selections={
            "azimuth": dataset.azimuths, "elevation": dataset.elevations,
            "frequency": dataset.frequencies, "polarization": dataset.polarizations})
        owner.plot_figure.set_size_inches(12., 7.)
        owner.plot_canvas = FigureCanvasAgg(owner.plot_figure)
        owner.combo_plot_scale.data = "linear"
        owner.chk_colorbar.setChecked(colorbar != "off")
        owner.chk_colorbar_shared.setChecked(colorbar == "shared")
        owner.image_analysis_controls = ImageAnalysisControls()
        owner.image_analysis_controls.restore_options({
            "horizontal_cuts": horizontal, "vertical_cuts": vertical})
        owners.append(owner)
        waterfall_mode.render(owner)
        return owner, owner.image_analysis_controls.controller

    yield create
    for owner in owners:
        owner._release_native_plot_samples()
        owner.plot_figure.clear()
        controls = owner.image_analysis_controls
        for widget in (controls.cut_bar, controls.combo_x, controls.combo_y, controls.combo_aggregation):
            widget.close()
            widget.deleteLater()
        controls.deleteLater()
    app.processEvents()


def assert_shared_cut_scales(controller):
    """Check displayed ranges, shared interaction, and coverage of every curve."""
    for direction in (0, 1):
        axes = [panel[1][direction] for panel in controller.panels]
        if axes[0] is None:
            assert all(axis is None for axis in axes)
            continue
        assert len(set(axes)) == len(controller.panels)
        limits = axes[0].get_ylim() if direction == 0 else axes[0].get_xlim()
        group = axes[0].get_shared_y_axes() if direction == 0 else axes[0].get_shared_x_axes()
        for axis, artists in zip(axes, controller.artists):
            actual = axis.get_ylim() if direction == 0 else axis.get_xlim()
            np.testing.assert_allclose(actual, limits)
            assert group.joined(axes[0], axis)
            values = artists[direction].get_ydata() if direction == 0 else artists[direction].get_xdata()
            assert min(limits) <= np.nanmin(values)
            assert max(limits) >= np.nanmax(values)


@pytest.mark.parametrize("horizontal,vertical", [(True, True), (True, False), (False, True)])
@pytest.mark.parametrize("colorbar", ["off", "shared", "individual"])
def test_dataset_cut_value_scales_are_shared_in_every_layout(rendered, horizontal, vertical, colorbar):
    owner, controller = rendered(horizontal=horizontal, vertical=vertical, colorbar=colorbar)
    assert len(controller.panels) == 2
    owner.plot_canvas.draw()
    assert_shared_cut_scales(controller)
    # The image's physical coordinate remains linked only to its own marginal.
    first, second = controller.panels
    first[0].set_xlim(.25, 1.75)
    first[0].set_ylim(8.25, 9.75)
    if horizontal:
        np.testing.assert_allclose(first[1][0].get_xlim(), [.25, 1.75])
        assert second[1][0].get_xlim() != first[1][0].get_xlim()
    if vertical:
        np.testing.assert_allclose(first[1][1].get_ylim(), [8.25, 9.75])
        assert second[1][1].get_ylim() != first[1][1].get_ylim()


def test_moving_cuts_shrinks_and_expands_the_shared_range_using_all_datasets(rendered):
    owner, controller = rendered(colorbar="individual")
    high_horizontal = controller.panels[0][1][0].get_ylim()
    high_vertical = controller.panels[0][1][1].get_xlim()
    controller.update(0., 8.)
    owner.plot_canvas.draw()
    assert_shared_cut_scales(controller)
    low_horizontal = controller.panels[0][1][0].get_ylim()
    low_vertical = controller.panels[0][1][1].get_xlim()
    assert low_horizontal[1] < 100. < high_horizontal[1]
    assert low_vertical[1] < 100. < high_vertical[1]
    controller.update(1., 9.)
    owner.plot_canvas.draw()
    assert_shared_cut_scales(controller)
    np.testing.assert_allclose(controller.panels[0][1][0].get_ylim(), high_horizontal)
    np.testing.assert_allclose(controller.panels[0][1][1].get_xlim(), high_vertical)


def test_manual_value_limits_propagate_between_datasets_without_changing_image_domains(rendered):
    _owner, controller = rendered()
    image_domains = [(image.get_xlim(), image.get_ylim()) for image, *_ in controller.panels]
    controller.panels[1][1][0].set_ylim(-25., 1250.)
    controller.panels[0][1][1].set_xlim(-50., 1500.)
    for (image, (horizontal, vertical), _record), (xlim, ylim) in zip(controller.panels, image_domains):
        np.testing.assert_allclose(horizontal.get_ylim(), [-25., 1250.])
        np.testing.assert_allclose(vertical.get_xlim(), [-50., 1500.])
        np.testing.assert_allclose(image.get_xlim(), xlim)
        np.testing.assert_allclose(image.get_ylim(), ylim)


def test_rebuilding_cut_layout_keeps_common_scales_and_selected_coordinates(rendered):
    owner, controller = rendered(colorbar="shared")
    controls = owner.image_analysis_controls
    controller.update(0., 8.)
    for horizontal, vertical in ((True, False), (False, False), (False, True), (True, True)):
        previous = controls.controller
        controls.check_horizontal.setChecked(horizontal)
        controls.check_vertical.setChecked(vertical)
        assert update_waterfall_display(owner)
        controller = controls.controller
        assert controller is not previous
        assert not previous.panels
        assert controller.position == controls.cut_position() == (0., 8.)
        assert_shared_cut_scales(controller)
