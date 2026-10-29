"""Bounded image comparison and reusable I/Q cursor preparation."""
from dataclasses import replace
import gc
import threading
import time
import tracemalloc
from unittest import mock

import numpy as np
import pytest

from GRIM_Backend.plotting import image_analysis as images, iq_tools
from GRIM_Backend.plotting.requests import PlotCancelled
from GRIM_Backend.ui.image_comparison import ImageComparisonDialog
from test_image_analysis import app, owner, settings, record
from test_iq_tools import cut


@pytest.mark.parametrize("mode", ["physical", "relative", "displayed"])
@pytest.mark.parametrize("policy", ["exact", "nearest", "linear"])
def test_tiles_preserve_values_across_reversed_axes_and_missing_samples(monkeypatch, mode, policy):
    monkeypatch.setattr(images, "COMPARISON_BLOCK_CELLS", 6)
    values = np.arange(1., 49.).reshape(6, 8)
    values[1, 2] = np.nan
    a = record(values, logarithmic=True); a.value_unit = "dBsm"
    b = replace(a, x=np.deg2rad(a.x[::-1]), y=a.y[::-1] * 1e9,
                values=(values - 3)[::-1, ::-1], x_unit="rad", y_unit="Hz")
    result = images.compare_records(a, b, policy=policy, mode=mode)
    expected = np.full(values.shape, 0. if mode == "relative" else 3.)
    expected[1, 2] = np.nan
    np.testing.assert_allclose(result["difference"], expected, atol=5e-14)
    np.testing.assert_allclose(result["a"], values-values[-1, -1] if mode == "relative" else values, atol=5e-14)


@pytest.mark.parametrize("axis", ["x", "y"])
def test_bilinear_physical_dbke_uses_each_corner_frequency(monkeypatch, axis):
    monkeypatch.setattr(images, "COMPARISON_BLOCK_CELLS", 3)
    from GRIM_Backend.datasets.constants import C0
    x, y = np.arange(9., 14.), np.arange(3., 7.)
    native = 1 + x[None, :] + 2*y[:, None]
    xa, ya = np.linspace(9., 13., 11), np.linspace(3., 6., 9)
    exact = 1 + xa[None, :] + 2*ya[:, None]
    frequency_b = x[None, :] if axis == "x" else y[:, None]
    frequency_a = xa[None, :] if axis == "x" else ya[:, None]
    b = replace(record(10*np.log10(native*2*np.pi*frequency_b*1e9/C0), logarithmic=True),
                x=x, y=y, x_axis="frequency" if axis == "x" else "azimuth",
                y_axis="azimuth" if axis == "x" else "frequency", x_unit="GHz" if axis == "x" else "deg",
                y_unit="deg" if axis == "x" else "GHz", quantity="sigma_2d", value_unit="dBke")
    a = replace(b, x=xa, y=ya, values=10*np.log10(exact*2*np.pi*frequency_a*1e9/C0))
    result = images.compare_records(a, b, policy="linear")
    np.testing.assert_allclose(result["difference"], 0, atol=2e-14)


def test_relative_peak_uses_source_outside_overlap_and_roi_uses_native_cells(monkeypatch):
    monkeypatch.setattr(images, "COMPARISON_BLOCK_CELLS", 2)
    a = record([[1, 5, 2, 100], [1, 3, 2, 50]])
    b = replace(a, x=a.x[:3], values=a.values[:, :3]*2)
    result = images.compare_records(a, b, mode="relative")
    np.testing.assert_allclose(result["difference"], -10*np.log10(20))
    stats = images.summarize_roi(result, (1, 2, 0, 1))
    assert stats["pixels"] == stats["selected_cells"] == 4
    assert stats["mean_delta"] == pytest.approx(-10*np.log10(20))


def test_bounded_display_retains_signed_extremes_and_true_cell_edges():
    a = record(np.zeros((8, 10)))
    a.values[0, 0], a.values[3, 4], a.values[7, 9] = 20, -50, 30
    b = replace(a, values=np.zeros((8, 10)))
    result = images.compare_records(a, b)
    display = images.comparison_display(result, max_side=2, max_cells=4)
    np.testing.assert_array_equal(display["difference"], [[-50, 0], [0, 30]])
    np.testing.assert_array_equal(display["a"], [[20, 0], [0, 30]])
    np.testing.assert_array_equal(display["x_edges"], [-.5, 4.5, 9.5])
    np.testing.assert_array_equal(display["y_edges"], [-.5, 3.5, 7.5])
    assert display["limits"] == (-50., 30.)
    assert images.summarize_roi(result)["mean_delta"] == 0.
    assert images.summarize_roi(result, (4, 4, 3, 3))["mean_delta"] == -50.


def test_phase_overview_uses_center_samples_and_roi_circular_mean(monkeypatch):
    monkeypatch.setattr(images, "COMPARISON_BLOCK_CELLS", 2)
    a = record([[179, -179, 178, -178], [-179, 179, -178, 178]], phase=True)
    a.quantity, a.value_unit = "phase", "deg"
    result = images.compare_records(a, replace(a, values=np.zeros((2, 4))))
    display = images.comparison_display(result, max_side=2, max_cells=4)
    np.testing.assert_array_equal(display["a"], [[179, 178], [-179, -178]])
    assert abs(images.summarize_roi(result)["mean_delta"]) == pytest.approx(180.)


def test_disk_comparison_and_roi_memory_are_bounded(tmp_path):
    a = record(np.arange(512*2048, dtype=float).reshape(512, 2048))
    b = replace(a, values=a.values*.5)
    tracemalloc.start()
    result = images.compare_records(a, b, storage="disk", cache_dir=tmp_path)
    _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    assert peak < 12*1024**2
    np.testing.assert_array_equal(result["difference"], a.values*.5)
    tracemalloc.start()
    stats = images.summarize_roi(result)
    _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    assert peak < 5*1024**2
    assert stats["mean_delta"] == pytest.approx(float(np.mean(a.values*.5)))
    del result; gc.collect()
    assert not list(tmp_path.glob("grim-result-*"))


def test_cancelled_compare_releases_partial_disk_output(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "COMPARISON_BLOCK_CELLS", 8)
    a = record(np.ones((20, 30)))
    calls = 0
    def cancelled():
        nonlocal calls
        calls += 1
        return calls > 4
    with pytest.raises(PlotCancelled):
        images.compare_records(a, a, storage="disk", cache_dir=tmp_path, cancel=cancelled)
    gc.collect()
    assert not list(tmp_path.glob("grim-result-*"))


def test_capture_close_waits_for_last_worker_lease():
    frozen = record().frozen()
    handle = frozen.storage._file
    first, second = frozen.lease(), frozen.lease()
    frozen.close(); first.close()
    assert not handle.closed
    np.testing.assert_array_equal(frozen.values, [[1, 2, 3], [4, 5, 6]])
    second.close()
    assert handle.closed and frozen.storage is None


def _wait(app, predicate, timeout=8):
    start = time.monotonic()
    while not predicate():
        app.processEvents()
        if time.monotonic()-start > timeout:
            raise AssertionError("Background comparison did not finish")
        time.sleep(.002)
    app.processEvents()


def _dialog():
    obj = owner(); obj.image_analysis_controls = settings()
    from GRIM_Backend.plotting.modes import waterfall_mode
    waterfall_mode.render(obj)
    return ImageComparisonDialog(obj)


def test_comparison_latest_request_wins_and_uses_worker_thread(app, monkeypatch):
    dialog = _dialog(); dialog._async_threshold = 0
    entered, release = threading.Event(), threading.Event()
    original = images.compare_records
    threads = []
    def delayed(*args, **kwargs):
        threads.append(threading.get_ident())
        if len(threads) == 1:
            entered.set(); assert release.wait(8)
        return original(*args, **kwargs)
    monkeypatch.setattr("GRIM_Backend.ui.image_comparison.compare_records", delayed)
    try:
        dialog.render()
        _wait(app, entered.is_set)
        dialog.combo_mode.setCurrentIndex(1)
        dialog.combo_mode.setCurrentIndex(2)
        release.set()
        _wait(app, lambda: dialog.result is not None and not dialog._runner.busy)
        assert dialog.result["unit"].startswith("numeric A")
        assert len(threads) == 2 and all(t != threading.get_ident() for t in threads)
    finally:
        release.set(); dialog.close()


def test_close_during_worker_does_not_dispose_mapped_capture_early(app, monkeypatch):
    dialog = _dialog(); dialog._async_threshold = 0
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    handles = [dialog.a.storage._file, dialog.b.storage._file]
    original = images.compare_records
    def delayed(*args, **kwargs):
        entered.set(); assert release.wait(8)
        try:
            # Check a source read even after the UI has closed. The lease must
            # protect the map until the cancelled worker leaves its batch.
            assert np.isfinite(args[0].values[0, 0])
            return original(*args, **kwargs)
        finally:
            finished.set()
    monkeypatch.setattr("GRIM_Backend.ui.image_comparison.compare_records", delayed)
    dialog.render(); _wait(app, entered.is_set)
    dialog.close()
    assert all(not handle.closed for handle in handles)
    release.set(); _wait(app, finished.is_set)
    _wait(app, lambda: all(handle.closed for handle in handles))


def test_swipe_and_blink_reuse_arrays_and_maintain_axes_clipping(app):
    dialog = _dialog()
    try:
        before_a, before_b = dialog.mesh_a.get_array(), dialog.mesh_overlay.get_array()
        dialog.combo_view.setCurrentIndex(2)
        with mock.patch("GRIM_Backend.ui.image_comparison.np.where", side_effect=AssertionError("full array swipe")):
            for value in (0, 10, 50, 100):
                dialog.swipe.setValue(value)
        assert dialog.mesh_a.get_array() is before_a and dialog.mesh_overlay.get_array() is before_b
        assert dialog.mesh_a.get_clip_path() is not None
        assert dialog.mesh_overlay.get_clip_path() is not None
        dialog.combo_view.setCurrentIndex(1)
        dialog._blink_b = True; dialog._update_primary()
        assert not dialog.mesh_a.get_visible() and dialog.mesh_overlay.get_visible()
        assert dialog.mesh_overlay.get_clip_path() is None
        assert dialog.mesh_overlay.get_clip_box() is dialog.image_axes[0].bbox
    finally:
        dialog.close()


@pytest.mark.parametrize("scaling", ["native", "common_peak", "phase_only"])
def test_repeat_preparation_reuses_alignment_and_phase_without_changing_readouts(monkeypatch, scaling):
    a = cut([1, 0, 1e-7j, 3j, np.nan+1j], x=[13, 12, 11, 10, 9], label="A")
    b = cut([2j, 2, -2j, 3], x=[10000, 11000, 12000, 13000], unit="MHz", label="B")
    unknown = cut([1, 2], x=[9.9, 10.1], label="No match")
    prepared = iq_tools.prepare_repeat_iq([a, b, unknown])
    # Preparation is the only place that may inspect full cuts for alignment
    # or unwrap/mask phase. Cursor reads only precomputed matches.
    with mock.patch.object(iq_tools, "aligned_cuts", side_effect=AssertionError("rematched")), \
         mock.patch.object(iq_tools, "phase_trace", side_effect=AssertionError("recomputed phase")):
        result = iq_tools.sample_repeat_iq(prepared, 11.2, scaling=scaling)
        assert result["coordinate"] == 11.
        np.testing.assert_array_equal(result["native_field"], [1e-7j, 2])
        np.testing.assert_array_equal(result["phase_valid"], [False, True])
        assert result["skipped"][0]["label"] == "No match"
        zero = iq_tools.sample_repeat_iq(prepared, 12, scaling=scaling)
        assert zero["native_field"][0] == 0
        assert not zero["phase_valid"][0]
        missing = iq_tools.sample_repeat_iq(prepared, 9, scaling=scaling)
        assert missing["count"] == 0


def test_repeat_prepared_nearest_tie_keeps_original_axis_order():
    a = cut([5, 2, 3], x=[11, 9, 10])
    prepared = iq_tools.prepare_repeat_iq([a])
    assert iq_tools.sample_repeat_iq(prepared, 10.5)["reference_index"] == 0
    assert iq_tools.sample_repeat_iq(prepared, 9.5)["reference_index"] == 1


@pytest.mark.parametrize("columns", [1, 3])
def test_swipe_endpoints_cover_complete_cells_including_singleton_x(app, columns):
    dialog = _dialog()
    try:
        dialog.a.close(); dialog.b.close()
        source = replace(record(np.arange(2*columns, dtype=float).reshape(2, columns)),
                         x=np.arange(columns, dtype=float)+10.)
        dialog.a, dialog.b = source.frozen(), replace(source, values=source.values+1).frozen()
        dialog.render(); dialog.combo_view.setCurrentIndex(2)
        left, right = dialog._display["x_edges"][[0, -1]]
        for value, boundary in ((0, left), (50, (left+right)/2), (100, right)):
            dialog.swipe.setValue(value)
            def bounds(mesh):
                path = mesh.get_clip_path().get_fully_transformed_path()
                vertices = dialog.image_axes[0].transData.inverted().transform(path.vertices)
                return vertices[:, 0].min(), vertices[:, 0].max()
            np.testing.assert_allclose(bounds(dialog.mesh_a), [left, boundary], atol=1e-12)
            np.testing.assert_allclose(bounds(dialog.mesh_overlay), [boundary, right], atol=1e-12)
        # At 0% A has zero area and B covers the full cell support; 100%
        # reverses this. A singleton column still has nonzero sweep width.
        assert right > left
    finally:
        dialog.close()
