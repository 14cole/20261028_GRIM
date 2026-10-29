"""Interactive pooling must never become the analysis or export data."""
from io import BytesIO
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.image import AxesImage

from GRIM_Backend.plotting.adaptive_image import draw_adaptive_image
from GRIM_Backend.plotting.image_analysis import attach_isar_record
from GRIM_Backend.plotting.image_display import _set_limits
from test_reconstruction_accuracy import harness, point_grid


def make_image(*, reverse=False):
    figure = Figure(figsize=(3, 3), dpi=60)
    canvas = FigureCanvasAgg(figure)
    ax = figure.add_subplot()
    values = np.zeros((503, 407), dtype=np.float32)
    values[201, 205], values[202, 205] = 100., 2.
    values[:30, :30] = np.nan
    x, y = np.arange(503.), np.arange(407.)
    if reverse:
        x, y = x[::-1], y[::-1]
    band = dict(x_range=x, y_range=y, az_values=np.array([-2., 2.]))
    artist = draw_adaptive_image(ax, band, values)
    canvas.draw()
    return figure, ax, artist, band, values


@pytest.mark.parametrize("reverse", [False, True])
def test_zoom_restores_native_detail_probes_and_home(reverse):
    figure, ax, artist, band, values = make_image(reverse=reverse)
    overview = artist.get_array().copy()
    assert overview.size < values.size / 4
    assert overview.max() == 100.
    assert np.ma.getmaskarray(overview)[0, 0]
    x, y = band["x_range"], band["y_range"]
    assert artist.probe(x[202], y[205]) == (x[202], y[205], 2.)
    assert artist.probe(-1000., 0.) is None
    original_limits = ax.get_xlim(), ax.get_ylim()
    ax.set_xlim(x[198], x[207])
    ax.set_ylim(y[200], y[211])
    figure.canvas.draw()
    assert 2. in artist.get_array()
    assert 100. in artist.get_array()
    assert artist._preview_key[2] == artist._preview_key[5] == 1
    np.testing.assert_array_equal(artist.native_values, values.T)
    ax.set_xlim(original_limits[0])
    ax.set_ylim(original_limits[1])
    figure.canvas.draw()
    np.testing.assert_array_equal(artist.get_array(), overview)


@pytest.mark.parametrize("format", ["png", "svg", "pdf"])
def test_export_draws_full_grid_and_restores_preview(format):
    figure, ax, artist, band, values = make_image()
    preview, extent = artist.get_array().copy(), artist.get_extent()
    original = AxesImage.make_image
    seen = []

    def capture(image, *args, **kwargs):
        if image is artist:
            seen.append(image.get_array().shape)
            np.testing.assert_array_equal(image.get_array().filled(np.nan), values.T)
            assert tuple(image.get_extent()) == artist.native_extent
        return original(image, *args, **kwargs)

    with mock.patch.object(AxesImage, "make_image", capture):
        figure.savefig(BytesIO(), format=format, bbox_inches="tight", dpi=120)
    assert seen and all(shape == values.T.shape for shape in seen)
    np.testing.assert_array_equal(artist.get_array(), preview)
    assert artist.get_extent() == extent


def test_failed_export_restores_preview():
    figure, ax, artist, band, values = make_image()
    preview, extent = artist.get_array().copy(), artist.get_extent()
    with mock.patch.object(AxesImage, "make_image", side_effect=RuntimeError("export failed")):
        with pytest.raises(RuntimeError, match="export failed"):
            figure.savefig(BytesIO(), format="png")
    np.testing.assert_array_equal(artist.get_array(), preview)
    assert artist.get_extent() == extent
    figure.canvas.draw()


def test_analysis_and_color_limits_use_full_data_after_zoom():
    figure, ax, artist, band, values = make_image()
    source = point_grid(np.linspace(-2., 2., 5), np.linspace(9e9, 11e9, 8))
    owner = harness(source)
    owner.combo_plot_scale.data = 'linear'
    attach_isar_record(owner, artist, band, dict(dataset=source, pol_idx=0,
        elevation_deg=0., unit_name='m', recon='fft'))
    record = artist._grim_image_record
    np.testing.assert_array_equal(record.values.filled(np.nan), values.T)
    assert record.values[205, 202] == 2.
    assert not any('Overview' in note for note in record.notes)
    ax.set_xlim(300, 310)
    ax.set_ylim(300, 310)
    figure.canvas.draw()
    assert artist.get_array().max() == 0.
    owner.spin_plot_zmin = owner.spin_plot_zmax = SimpleNamespace(value=lambda: 0.)
    _set_limits(owner, [artist], shared=True, mode='isar_image')
    assert artist.get_clim() == (0., 100.)
    np.testing.assert_array_equal(record.values.filled(np.nan), values.T)


def test_resize_changes_preview_without_reconstruction():
    figure, ax, artist, band, values = make_image()
    count = artist.get_array().size
    figure.set_size_inches(8, 8)
    figure.canvas.draw()
    assert artist.get_array().size > count
    np.testing.assert_array_equal(artist.native_values, values.T)


def test_peak_scaling_includes_peak_outside_zoom():
    from GRIM_Backend.plotting.actions import PlotOpsMixin
    from test_plot_renderer_correctness import _Spin
    figure, ax, artist, band, values = make_image()
    ax.set_xlim(300., 310.)
    ax.set_ylim(300., 310.)
    figure.canvas.draw()
    owner = SimpleNamespace(last_plot_mode='isar_image',
        _current_isar_image_meshes=lambda: [artist],
        _plot_scale_is_linear=lambda: True,
        spin_plot_zmin=_Spin(0.), spin_plot_zmax=_Spin(0.),
        spin_isar_peak_drop=_Spin(20.), _on_isar_clim_changed=lambda: None,
        status=SimpleNamespace(showMessage=lambda text: None))
    PlotOpsMixin._on_isar_peak_scale(owner)
    assert owner.spin_plot_zmin.value() == 1.
    assert owner.spin_plot_zmax.value() == 100.
