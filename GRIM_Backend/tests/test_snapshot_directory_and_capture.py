"""Plot snapshots follow the selected working folder; captures freeze off the UI thread."""
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from GRIM_Backend.datasets.result_storage import array_storage, operation_result_storage
from GRIM_Backend.plotting import image_analysis as images
from GRIM_Backend.plotting.actions import PlotOpsMixin
from GRIM_Backend.plotting.modes import common
from GRIM_Backend.plotting.requests import PlotCancelled
from test_image_analysis import app, owner, settings, record
from test_comparison_workspaces import _dialog, _wait


@pytest.fixture
def snapshot_dir(tmp_path):
    folder = tmp_path / "snapshots"
    folder.mkdir()
    common.configure_snapshot_directory(folder)
    try:
        yield folder
    finally:
        common.configure_snapshot_directory(None)


def _recorded_dirs(monkeypatch):
    seen = []
    original = common.tempfile.TemporaryFile

    def tracked(*args, **kwargs):
        seen.append(kwargs.get("dir"))
        return original(*args, **kwargs)

    monkeypatch.setattr(common.tempfile, "TemporaryFile", tracked)
    return seen


def test_snapshots_use_the_configured_folder_unless_a_disk_policy_names_one(tmp_path, snapshot_dir, monkeypatch):
    seen = _recorded_dirs(monkeypatch)
    storage = common.NativeSamples((3, 2))
    assert not storage.closed
    storage.close()
    assert storage.closed
    other = tmp_path / "policy"
    other.mkdir()
    with operation_result_storage("disk", cache_dir=str(other)):
        common.NativeSamples.image(np.ones((2, 2))).close()
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    common.NativeSamples((1, 1), directory=explicit).close()
    assert seen == [str(snapshot_dir), str(other), str(explicit)]
    common.configure_snapshot_directory(None)
    common.NativeSamples((1, 1)).close()
    assert seen[-1] == common.tempfile.gettempdir()
    with pytest.raises(OSError, match="unavailable"):
        common.NativeSamples((1, 1), directory=tmp_path / "missing")


def test_frozen_records_and_comparison_scratch_follow_the_folder(snapshot_dir, monkeypatch):
    seen = _recorded_dirs(monkeypatch)
    source = record(np.arange(12., dtype=float).reshape(3, 4))
    frozen = source.frozen()
    try:
        assert seen == [str(snapshot_dir)]
        np.testing.assert_array_equal(frozen.values, source.values)
    finally:
        frozen.close()
    result = images.compare_records(source, source, storage="disk")
    assert array_storage(result["difference"]) == "disk"
    assert any(entry.name.startswith("grim-result-") for entry in snapshot_dir.iterdir())
    np.testing.assert_array_equal(result["difference"], 0.)
    del result


def test_frozen_copy_can_be_cancelled_and_closes_its_file(snapshot_dir, monkeypatch):
    handles = []
    original = common.tempfile.TemporaryFile

    def tracked(*args, **kwargs):
        handle = original(*args, **kwargs)
        handles.append(handle)
        return handle

    monkeypatch.setattr(common.tempfile, "TemporaryFile", tracked)
    with pytest.raises(PlotCancelled):
        record(np.ones((2, 3))).frozen(cancel=lambda: True)
    assert len(handles) == 1 and handles[0].closed


def test_artist_release_waits_for_a_capture_lease():
    native = common.NativeSamples.image(np.arange(6.).reshape(2, 3))
    live = record(native.values.T)
    assert live.storage is None
    artist = SimpleNamespace(_grim_native_samples=native, _grim_image_record=live,
                             _grim_native_rectilinear_data=object())
    lease = live.lease()
    PlotOpsMixin._release_artist_native_samples(artist)
    assert artist._grim_native_samples is None and artist._grim_image_record is None
    assert artist._grim_native_rectilinear_data is None
    assert not native.closed  # the capture still reads the mapping
    np.testing.assert_array_equal(native.values[0], [0., 1., 2.])
    lease.close()
    assert native.closed
    other = common.NativeSamples.image(np.ones((1, 1)))
    PlotOpsMixin._release_artist_native_samples(SimpleNamespace(_grim_native_samples=other,
                                                                _grim_image_record=None))
    assert other.closed


def test_large_captures_freeze_on_a_worker_thread_and_replace_the_side(app):
    dialog = _dialog()
    try:
        first = dialog.a
        assert first is not None
        expected = np.array(first.values, copy=True)
        dialog._async_threshold = 0
        dialog.combo_source.setCurrentIndex(0)  # the panel A was captured from
        dialog.capture("a")
        assert dialog.a is first
        assert "Capturing A" in dialog.advisory.text()
        _wait(app, lambda: dialog.a is not first and not dialog._capture_runners["a"].busy)
        assert first.storage is None  # the replaced capture released its file
        np.testing.assert_array_equal(dialog.a.values, expected)
        assert "Capturing" not in dialog.advisory.text()
    finally:
        dialog.close()
    assert dialog.a is None


def test_closing_the_dialog_discards_a_capture_still_in_flight(app, monkeypatch):
    dialog = _dialog()
    dialog._async_threshold = 0
    frozen_records, release = [], threading.Event()
    original = images.ImageRecord.frozen

    def blocking(self, **kwargs):
        frozen = original(self, **kwargs)
        frozen_records.append(frozen)
        assert release.wait(8)
        return frozen

    monkeypatch.setattr(images.ImageRecord, "frozen", blocking)
    dialog.capture("b")
    _wait(app, lambda: bool(frozen_records))
    dialog.close()
    assert frozen_records[0].storage is not None  # still owned by the worker
    release.set()
    _wait(app, lambda: frozen_records[0].storage is None)
    assert dialog.b is None


def test_cancelled_capture_before_any_copy_leaves_no_snapshot(app, monkeypatch):
    dialog = _dialog()
    dialog._async_threshold = 0
    created = []
    original = common.NativeSamples.__init__

    def tracking(self, shape, *, directory=None):
        original(self, shape, directory=directory)
        created.append(self)

    monkeypatch.setattr(common.NativeSamples, "__init__", tracking)
    dialog.capture("b")
    dialog.close()  # cancels the pending copy at its first block
    _wait(app, lambda: not dialog._capture_runners["b"].busy)
    assert all(storage.closed for storage in created)
