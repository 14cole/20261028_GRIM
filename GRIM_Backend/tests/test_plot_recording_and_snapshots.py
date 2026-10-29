"""GUI plots reach the recorded script, and failed publications cannot unmap live plots."""
import os
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

import GRIM_Backend.ui.app as grim_app
from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.plotting.actions import PlotOpsMixin
from GRIM_Backend.plotting.modes.common import NativeSamples
from GRIM_Backend.plotting.registry import HEADLESS_PLOT_MODES
from GRIM_Backend.plotting.requests import PlotResult
from GRIM_Backend.scripting.recorder import DatasetReference, PythonScriptRecorder
from test_gui_shell import (
    _FakeFeatureWorkflow, _FakeFreddyIntegration, _FakeGhostIntegration, _MemorySettings, _RecordingWindow,
)
from test_plot_renderer_correctness import _grid
from test_python_recorder import PythonRecorderTests


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    patches = (
        mock.patch.object(grim_app, "GhostIntegrationWidget", _FakeGhostIntegration),
        mock.patch.object(grim_app, "load_ghost_module", return_value=_FakeFeatureWorkflow()),
        mock.patch.object(grim_app, "FreddyIntegrationWidget", _FakeFreddyIntegration),
    )
    for patch in patches:
        patch.start()
    try:
        win = _RecordingWindow(settings=_MemorySettings())
        yield win
    finally:
        win.ghost_integration.running = False
        win.freddy_integration.running = False
        win.deleteLater()
        app.processEvents()
        for patch in reversed(patches):
            patch.stop()


def test_disposing_a_failed_result_keeps_snapshots_owned_by_artists():
    attached = NativeSamples.image(np.arange(6.0).reshape(2, 3))
    unpublished = NativeSamples.image(np.ones((2, 2)))
    artist = SimpleNamespace()
    edges = (np.arange(3.0), np.arange(4.0))
    PlotOpsMixin._attach_native_image_snapshot(artist, (*edges, attached))
    result = PlotResult(request=None, items=[{"snapshot": (*edges, attached)},
                                             {"snapshot": (*edges, unpublished)}])
    result.close()                       # what a failed publication triggers
    try:
        assert not attached.closed
        assert unpublished.closed
        np.testing.assert_array_equal(artist._grim_native_rectilinear_data[2][0], [0.0, 3.0])
    finally:
        attached.close()


def test_recorder_accepts_every_headless_plot_mode(tmp_path):
    source = tmp_path / "source.grim"
    _grid().save(source)
    reference = DatasetReference("dataset-id", "Measured", str(source))
    for mode in sorted(HEADLESS_PLOT_MODES):
        recorder = PythonScriptRecorder()
        recorder.bind_loaded(reference)
        assert recorder.record_plot([reference], names=["Measured"], mode=mode, parameters={}) is not None, mode
    refused = PythonScriptRecorder()
    refused.bind_loaded(reference)
    assert refused.record_plot([reference], names=["Measured"], mode="sector_stats", parameters={}) is None


@pytest.mark.parametrize("mode", ["cdf", "waterfall"])
def test_gui_cdf_and_waterfall_specs_replay_headlessly(window, tmp_path, mode):
    source = tmp_path / "source.grim"
    _grid().save(source)
    window._add_dataset_row(RcsGrid.load(source), "Measured", "", file_name=str(source))
    window.table.selectRow(0)
    window.list_az.selectAll()
    window.list_elev.selectAll()
    window.list_freq.selectAll()
    window.list_pol.clearSelection()
    window.list_pol.item(0).setSelected(True)

    window._record_python_plot(mode, emit=False)
    spec = window.last_python_plot_spec
    assert spec[0] == "supported", spec
    assert spec[3] == mode

    recorder = PythonScriptRecorder()
    for reference in spec[1]:
        recorder.bind_loaded(reference)
    assert recorder.record_plot(spec[1], names=spec[2], mode=spec[3], parameters=spec[4]) is not None
    image = tmp_path / f"{mode}.png"
    recorder.record_plot_save(str(image), dpi=80)
    script = tmp_path / f"{mode}_recipe.py"
    script.write_text(recorder.script, encoding="utf-8")
    completed = PythonRecorderTests._run_script(script, tmp_path)
    assert completed.returncode == 0, completed.stderr[-2000:]
    assert image.is_file() and image.stat().st_size > 100
