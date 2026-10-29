"""Exact RF outputs, bounded reads, and display changes without recomputation."""
from types import SimpleNamespace
from unittest import mock
import threading
import unittest

import numpy as np
import pytest
from PySide6.QtCore import QThread

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.isar.geometry import pool_image_peaks
from GRIM_Backend.plotting.requests import PlotPlan, PlotRequest, PlotCancelled
from GRIM_Backend.plotting.modes import az_vs_range_mode as az, isar_mode, waterfall_mode
from GRIM_Backend.plotting.image_display import update_image_style, update_waterfall_display
import test_image_analysis as image_helpers
import test_analysis_background as background
from test_waterfall_cut_alignment import assert_drawn_alignment


def request(*, sign='+jwt', normalize=False, scale='linear', irregular=False):
    rng = np.random.default_rng(85)
    field = (rng.normal(size=(19, 64)) + 1j * rng.normal(size=(19, 64))).astype(np.complex64)
    field[3, 9:13] = np.nan
    field[-1] = np.nan
    freq = np.linspace(8., 10., 64)
    if irregular:
        freq[32:] += .5
    grid = RcsGrid(np.arange(19.), [0.], freq, ['VV'], rcs=field[:, None, :, None],
        units={'frequency': 'GHz', 'azimuth': 'deg', 'elevation': 'deg', 'time_convention': f'exp({sign})'})
    req = PlotRequest('az_vs_range', grid, (PlotPlan('A', grid, (np.arange(19), [0], np.arange(64), [0])),),
        scale=scale, options=dict(window='Hanning', unit_name='m', unit_scale=1., peak_norm=normalize,
            azimuth_width=1., time_sign=sign))
    return grid, req


@pytest.mark.parametrize('normalize', [False, True])
@pytest.mark.parametrize('sign', ['+jwt', '-jwt'])
@pytest.mark.parametrize('scale', ['linear', 'dbsm'])
@pytest.mark.parametrize('irregular', [False, True])
def test_az_range_batches_are_numerically_identical(normalize, sign, scale, irregular):
    grid, req = request(sign=sign, normalize=normalize, scale=scale, irregular=irregular)
    source = grid.rcs[:, 0, :, 0]
    if sign == '-jwt':
        source = np.conj(source)
    target, history, weights, _ = az._prepare_uniform_frequency_history(grid.frequencies * 1e9, source)
    n_fft = az._range_fft_size(len(target), len(grid.azimuths))
    formed, _ = az._form_range_image(history, weights, np.hanning(len(target)), n_fft=n_fft)
    magnitude = abs(formed)
    if normalize:
        magnitude /= np.nanmax(magnitude)
    expected = az._range_display_values(grid, magnitude, linear=scale == 'linear')
    with mock.patch.object(grid, 'rcs_slice', wraps=grid.rcs_slice) as read:
        result = az.prepare_azimuth_range(req, batch_bytes=100)
    assert read.call_count == 19
    actual = result.items[0]['display']
    np.testing.assert_array_equal(np.isnan(actual), np.isnan(expected))
    # Recent pocketfft versions vectorize batched transforms differently. Test
    # their single-precision accuracy in amplitude space (dB exaggerates tiny
    # absolute errors at deep nulls), without demanding bitwise FFT identity.
    to_amplitude = np.sqrt if scale == 'linear' else lambda x: 10.0 ** (x / 20.0)
    expected_amplitude = to_amplitude(expected)
    np.testing.assert_allclose(to_amplitude(actual), expected_amplitude, rtol=0,
        atol=8 * np.finfo(np.float32).eps * np.nanmax(expected_amplitude))
    np.testing.assert_allclose(result.items[0]['range_axis'],
        np.fft.fftshift(np.fft.fftfreq(n_fft, d=np.mean(np.diff(target)))) * 299792458 / 2)


def test_az_range_cancel_stops_before_next_batch():
    grid, req = request()
    with mock.patch.object(grid, 'rcs_slice', wraps=grid.rcs_slice) as read:
        with pytest.raises(PlotCancelled):
            az.prepare_azimuth_range(req, cancel=lambda: read.call_count >= 3, batch_bytes=100)
    assert read.call_count == 3


def test_range_fft_batches_match_double_precision_dft():
    grid, _ = request(irregular=True)
    target, history, weights, _ = az._prepare_uniform_frequency_history(
        grid.frequencies * 1e9, grid.rcs[:, 0, :, 0])
    taper = np.hanning(len(target)).astype(np.float32)
    n = az._range_fft_size(len(target), len(grid.azimuths))
    # Independent direct Fourier sum; no production FFT or gain helper.
    weighted = history.astype(np.complex128) * weights * taper
    kernel = np.exp(2j * np.pi * np.outer(np.arange(len(target)), np.arange(n)) / n)
    gain = np.sum(weights * taper, axis=1, dtype=np.float64)
    usable = gain > 0
    reference = np.fft.fftshift(weighted[usable] @ kernel / gain[usable, None], axes=1)
    full, _ = az._form_range_image(history, weights, taper, n_fft=n)
    single = np.concatenate([az._form_range_image(history[i:i+1], weights[i:i+1],
        taper, n_fft=n)[0] for i in range(len(history))])
    for formed in (full, single):
        np.testing.assert_allclose(formed[usable], reference, rtol=0,
            atol=8 * np.finfo(np.float32).eps * np.max(abs(reference)))
        assert np.all(np.isnan(formed[~usable]))
@pytest.mark.parametrize('stride,max_cells', [(1, 9), (4, 9), (19, 9), (4, 100)])
def test_tiled_peak_reduction_preserves_ties_missing_values_and_native_indices(stride, max_cells):
    data = np.full((31, 17), 3.)
    data[0:stride, 0:4] = np.nan
    data[11, 13] = 10.
    data[11, 12] = 10.
    blocks = [(0, 4), None, (4, 17)]
    values, iy, ix = pool_image_peaks(data, stride, blocks, max_cells=max_cells)
    for j, block in enumerate(blocks):
        for i in range(values.shape[0]):
            if block is None:
                assert np.isnan(values[i, j]) and iy[i, j] == ix[i, j] == -1
                continue
            sample = data[i*stride:min(len(data), (i+1)*stride), slice(*block)]
            if not np.any(np.isfinite(sample)):
                assert np.isnan(values[i, j])
                continue
            k = np.nanargmax(sample)
            assert values[i, j] == sample.flat[k]
            assert (iy[i, j], ix[i, j]) == (i*stride + k // sample.shape[1], block[0] + k % sample.shape[1])


def test_waterfall_relayouts_keep_images_native_samples_and_zoom():
    owner = image_helpers.owner()
    owner.plot_figure.set_size_inches(12, 8)
    owner.combo_plot_scale.data = 'linear'
    options = dict(horizontal=True, vertical=True)
    owner.image_analysis_controls = SimpleNamespace(axes=lambda: ('azimuth', 'frequency'),
        aggregation=lambda: 'panels', linked_cuts=lambda: True,
        horizontal_cuts=lambda: options['horizontal'], vertical_cuts=lambda: options['vertical'],
        bind=lambda controller: None)
    waterfall_mode.render(owner)
    state = owner.plot_figure._grim_waterfall_display
    meshes, records = list(state['meshes']), list(state['records'])
    for ax in state['axes']:
        ax.set_xlim(.25, 1.75)
        ax.set_ylim(8.25, 10.75)
    with mock.patch.object(owner.active_dataset, 'power_slice', side_effect=AssertionError('must reuse pixels')):
        for horizontal, vertical, shown, shared in [(False, False, False, True), (True, False, True, False),
                                                  (False, True, True, True), (True, True, True, True)]:
            options.update(horizontal=horizontal, vertical=vertical)
            owner.chk_colorbar.setChecked(shown)
            owner.chk_colorbar_shared.setChecked(shared)
            assert update_waterfall_display(owner)
            assert state['meshes'] == meshes and state['records'] == records
            owner.plot_canvas.draw()
            controller = owner.plot_figure._grim_linked_cuts
            assert_drawn_alignment(controller)
            for ax in state['axes']:
                np.testing.assert_allclose(ax.get_xlim(), [.25, 1.75])
                np.testing.assert_allclose(ax.get_ylim(), [8.25, 10.75])
                assert len(ax.lines) == int(horizontal) + int(vertical)
        owner.spin_plot_zmin.setValue(5.)
        owner.spin_plot_zmax.setValue(20.)
        assert update_image_style(owner)
        assert all(mesh.get_clim() == (5., 20.) for mesh in meshes)
    owner._release_native_plot_samples()
    assert owner.plot_figure._grim_waterfall_display is None


def test_isar_digest_cache_only_accepts_proven_immutable_buffers():
    grid, _ = request()
    args = (np.arange(19), 0, np.arange(64), 0)
    first = isar_mode._selected_data_token(grid, *args)
    assert not getattr(grid, '_isar_immutable_digests', {})
    grid._complex = np.frombuffer(grid._complex.tobytes(), dtype=grid._complex.dtype).reshape(grid.shape)
    assert isar_mode._selected_data_token(grid, *args) == first
    assert len(grid._isar_immutable_digests) == 1
    with mock.patch.object(isar_mode.np, 'ascontiguousarray', wraps=np.ascontiguousarray) as contiguous:
        assert isar_mode._selected_data_token(grid, *args) == first
    # Only coordinate/metadata arrays are hashed again, no sample block.
    assert all(np.asarray(call.args[0]).ndim < 2 for call in contiguous.call_args_list)
    grid.units['phase_reference'] = 'changed'
    assert isar_mode._selected_data_token(grid, *args) != first
    grid.rcs_phase[:] = .5
    mutable = isar_mode._selected_data_token(grid, *args)
    grid.rcs_phase[:] = .6
    assert isar_mode._selected_data_token(grid, *args) != mutable


def test_image_colorbar_and_limits_update_existing_artists_without_layout_drift():
    owner = image_helpers.owner()
    owner.combo_plot_scale.data = 'linear'
    owner.plot_figure.clear()
    owner.plot_figure.set_layout_engine('constrained')
    axes = list(owner.plot_figure.subplots(1, 2))
    owner.plot_axes, owner.plot_ax = axes, axes[0]
    owner.last_plot_mode = 'isar_image'
    meshes = [ax.imshow(np.arange(12.).reshape(3, 4) + i * 20, aspect='auto') for i, ax in enumerate(axes)]
    owner._isar_meshes = meshes
    owner.plot_colorbars = []
    owner.chk_colorbar.setChecked(False)
    owner.chk_colorbar_shared.setChecked(False)
    owner.plot_canvas.draw()
    positions = [ax.get_position().bounds for ax in axes]
    for _ in range(3):
        owner.chk_colorbar.setChecked(True)
        owner.chk_colorbar_shared.setChecked(True)
        assert update_image_style(owner)
        assert len(owner.plot_colorbars) == 1
        assert meshes[0].get_clim() == meshes[1].get_clim() == (0., 31.)
        owner.chk_colorbar_shared.setChecked(False)
        assert update_image_style(owner)
        assert len(owner.plot_colorbars) == 2
        assert meshes[0].get_clim() == (0., 11.)
        assert meshes[1].get_clim() == (20., 31.)
        owner.spin_plot_zmin.setValue(2.)
        owner.spin_plot_zmax.setValue(5.)
        assert update_image_style(owner)
        assert all(mesh.get_clim() == (2., 5.) for mesh in meshes)
        owner.spin_plot_zmin.setValue(0.)
        owner.spin_plot_zmax.setValue(0.)
        owner.chk_colorbar.setChecked(False)
        assert update_image_style(owner)
        owner.plot_canvas.draw()
        for ax, expected in zip(axes, positions):
            np.testing.assert_allclose(ax.get_position().bounds, expected, rtol=0, atol=.002)
        assert [list(ax.images)[0] for ax in axes] == meshes


def test_hiding_initial_single_colorbar_restores_original_axes_slot_without_layout_engine():
    owner = image_helpers.owner()
    owner.plot_figure.clear()
    owner.plot_figure.set_layout_engine(None)
    owner.plot_ax = owner.plot_figure.add_subplot(111)
    owner.plot_axes = None
    owner.last_plot_mode = 'az_vs_range'
    initial = owner.plot_ax.get_position().bounds
    mesh = owner.plot_ax.imshow(np.arange(12.).reshape(3, 4), aspect='auto')
    owner.plot_colorbars = [owner.plot_figure.colorbar(mesh, ax=owner.plot_ax)]
    assert owner.plot_ax.get_position().width < initial[2]
    for _ in range(3):
        owner.chk_colorbar.setChecked(False)
        assert update_image_style(owner)
        np.testing.assert_allclose(owner.plot_ax.get_position().bounds, initial, rtol=0, atol=1e-12)
        owner.chk_colorbar.setChecked(True)
        assert update_image_style(owner)


class BackgroundAzRangeTests(unittest.TestCase):
    setUpClass = classmethod(background.BackgroundAnalysisTests.setUpClass.__func__)
    tearDownClass = classmethod(background.BackgroundAnalysisTests.tearDownClass.__func__)
    setUp = background.BackgroundAnalysisTests.setUp
    tearDown = background.BackgroundAnalysisTests.tearDown
    load_sample = background.BackgroundAnalysisTests.load_sample
    wait = background.BackgroundAnalysisTests.wait

    def test_range_cine_waits_for_background_publication_before_next_step(self):
        self.load_sample()
        self.window.list_pol.clearSelection()
        self.window.list_pol.item(0).setSelected(True)
        self.window.last_plot_mode = 'az_vs_range'
        self.window._isar_play_mode = 'az_vs_range'
        play = self.window.btn_isar_ap_play
        blocked = play.blockSignals(True)
        play.setChecked(True)
        play.blockSignals(blocked)
        self.window._plot_async_threshold = 0
        started, release = threading.Event(), threading.Event()
        original = az.prepare_azimuth_range
        def slow(*args, **kwargs):
            started.set()
            release.wait(5)
            return original(*args, **kwargs)
        with mock.patch.object(az, 'prepare_azimuth_range', side_effect=slow), \
                mock.patch.object(self.window, '_isar_step_aperture', side_effect=lambda _: self.window._plot_az_vs_range()), \
                mock.patch('GRIM_Backend.plotting.actions.QTimer.singleShot') as schedule:
            self.window._isar_play_step()
            self.wait(started.is_set)
            assert play.isChecked()
            assert not schedule.called
            release.set()
            runner = self.window._plot_contexts['plotting'].session.runner
            self.wait(lambda: not runner.busy)
            assert play.isChecked()
            frames = [call for call in schedule.call_args_list if call.args[0] == 30]
            assert len(frames) == 1
            old_callback = frames[0].args[1]
            play.setChecked(False)
            with mock.patch.object(self.window, '_isar_step_aperture') as step:
                old_callback()
                step.assert_not_called()

    def test_waterfall_display_edits_preserve_frozen_selection_recipe(self):
        data = self.load_sample()
        self.window._plot_waterfall()
        original = self.window.last_python_plot_spec
        assert original[3] == 'waterfall'
        controls = self.window.image_analysis_controls
        listing = self.window.list_freq
        blocked = listing.blockSignals(True)
        listing.item(0).setSelected(False)
        listing.blockSignals(blocked)
        with mock.patch.object(data, 'power_slice', side_effect=AssertionError('display edit must not read dataset')):
            controls.check_horizontal.setChecked(False)
            self.window.chk_colorbar.setChecked(False)
            self.window.spin_plot_zmin.setValue(-10.)
            self.window.spin_plot_zmax.setValue(10.)
        updated = self.window.last_python_plot_spec
        assert updated[4]['frequencies'] == original[4]['frequencies']
        assert updated[4]['heatmap_options']['horizontal_cuts'] is False
        assert updated[4]['show_colorbar'] is False
        assert updated[4]['color_limits'] == (-10., 10.)

    def test_latest_range_request_wins_and_clear_cancels_publication(self):
        self.load_sample()
        self.window.list_pol.clearSelection()
        self.window.list_pol.item(0).setSelected(True)
        self.window._plot_async_threshold = 0
        started, release = threading.Event(), threading.Event()
        original = az.prepare_azimuth_range
        threads = []
        requests = []
        def slow(*args, **kwargs):
            threads.append(QThread.currentThread())
            requests.append(args[0])
            started.set()
            release.wait(5)
            return original(*args, **kwargs)
        with mock.patch.object(az, 'prepare_azimuth_range', side_effect=slow):
            self.window._plot_az_vs_range()
            self.wait(started.is_set)
            blocked = self.window.list_pol.blockSignals(True)
            self.window.list_pol.clearSelection()
            self.window.list_pol.item(1).setSelected(True)
            self.window.list_pol.blockSignals(blocked)
            expected_pol = self.window._selected_values(self.window.list_pol)[0]
            self.window._plot_az_vs_range()
            release.set()
            runner = self.window._plot_contexts['plotting'].session.runner
            self.wait(lambda: not runner.busy)
        assert all(thread != self.app.thread() for thread in threads)
        record = self.window._az_vs_range_mesh._grim_image_record
        assert record.metadata['polarization'] == expected_pol
        assert len(requests) == 2
        assert requests[0].plans[0].selection[3].tolist() != requests[1].plans[0].selection[3].tolist()
        started.clear()
        release.clear()
        with mock.patch.object(az, 'prepare_azimuth_range', side_effect=slow):
            self.window._plot_az_vs_range()
            self.wait(started.is_set)
            self.window._clear_plot()
            release.set()
            self.wait(lambda: not runner.busy)
        assert not self.window.plot_ax.images and not self.window.plot_ax.collections
