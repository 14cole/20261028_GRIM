"""Temporary data follows the user's folder and storage choices, and nothing leaks between operations."""
import gc
import json
import os
import threading
import time
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

import GRIM_Backend.assembly.tree as tree_module
import GRIM_Backend.ui.app as grim_app
import GRIM_Backend.ui.dataset_actions as actions_module
import GRIM_Backend.ui.result_storage_options as options_module
from GRIM_Backend.datasets.reduction_workspace import workspace_array
from GRIM_Backend.datasets.result_storage import (
    _retry_cleanup, allocate_result, application_result_storage_info, array_storage,
    configure_auto_ram_budget, operation_result_storage,
)
from GRIM_Backend.execution.dataset_jobs import _BackgroundCallableWorker
from GRIM_Backend.plotting.modes.common import StreamingEnvelope, configure_snapshot_directory
from GRIM_Backend.reports.workspace import _sweep_abandoned_preview_folders
from test_gui_shell import (
    _FakeFeatureWorkflow, _FakeFreddyIntegration, _FakeGhostIntegration, _MemorySettings, _RecordingWindow,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def working_folder(tmp_path):
    folder = tmp_path / "working"
    folder.mkdir()
    configure_snapshot_directory(folder)
    try:
        yield folder
    finally:
        configure_snapshot_directory(None)


def _owner_folder(array):
    return Path(array._result_owner.path)


def test_scoped_application_budget_leaves_the_global_setting_alone():
    configure_auto_ram_budget(None)
    seen_elsewhere = []
    with operation_result_storage("auto", application_ram_budget_bytes=1024):
        assert application_result_storage_info()["ram_budget_bytes"] == 1024
        other = threading.Thread(target=lambda: seen_elsewhere.append(
            application_result_storage_info()["ram_budget_bytes"]))
        other.start()
        other.join()
    assert seen_elsewhere and seen_elsewhere[0] != 1024
    assert application_result_storage_info()["automatic"] is True


def test_allocations_without_a_folder_follow_the_working_folder(working_folder, tmp_path):
    with operation_result_storage("disk"):
        result = allocate_result((16,), np.float64)
    assert _owner_folder(result).parent == working_folder
    outer = tmp_path / "outer"
    outer.mkdir()
    with operation_result_storage("disk", cache_dir=outer):
        with operation_result_storage("auto", ram_budget_bytes=0):   # nested scratch scope
            nested = allocate_result((16,), np.float64)
    assert _owner_folder(nested).parent == outer


def test_workspaces_and_sweep_spools_follow_the_working_folder(working_folder):
    scratch = workspace_array((2_000_000,), np.float64)       # above the RAM workspace limit
    assert array_storage(scratch) == "disk"
    assert _owner_folder(scratch).parent == working_folder
    envelope = StreamingEnvelope(phase_degrees=True)
    envelope.update(np.arange(5.0))
    try:
        assert Path(envelope._phase_file.name).parent == working_folder
    finally:
        envelope._phase_file.close()


def test_independent_copies_do_not_pin_the_temporary_folder(tmp_path):
    with operation_result_storage("disk", cache_dir=tmp_path):
        original = allocate_result((1000,), np.float64, fill=1.0)
    folder = _owner_folder(original)
    view = original[10:]
    doubled = original * 2
    copied = original.copy()
    del original
    gc.collect()
    assert folder.exists()                      # the view still uses the file
    del view
    gc.collect()
    _retry_cleanup()
    assert not folder.exists()                  # copies never pinned it
    assert doubled[0] == 2.0 and copied[0] == 1.0


def test_only_old_empty_preview_folders_are_swept(tmp_path):
    old_empty = tmp_path / "grim-ppt-preview-old"
    old_full = tmp_path / "grim-ppt-preview-full"
    fresh = tmp_path / "grim-ppt-preview-new"
    for folder in (old_empty, old_full, fresh):
        folder.mkdir()
    (old_full / "slide.png").write_bytes(b"png")
    stale = time.time() - 3 * 24 * 3600
    for folder in (old_empty, old_full):
        os.utime(folder, (stale, stale))
    assert _sweep_abandoned_preview_folders([tmp_path]) == 1
    assert not old_empty.exists() and old_full.exists() and fresh.exists()


def test_report_previews_live_in_the_working_folder(app, working_folder):
    from GRIM_Backend.reports.workspace import PptWorkspace
    workspace = PptWorkspace()
    try:
        assert Path(workspace._preview_temp.name).parent == working_folder
    finally:
        workspace.dispose()
        workspace.deleteLater()


def test_assembly_build_runs_under_the_chosen_storage(tmp_path, monkeypatch):
    def fake_build(snapshot, axis_mode, cancel_check, report=None):
        return allocate_result((1000,), np.float64), "history"

    monkeypatch.setattr(tree_module, "build_assembly_grid", fake_build)
    results = []
    worker = tree_module._AssemblyBuildWorker(
        object(), "intersect", threading.Event(),
        storage_options={"mode": "disk", "cache_dir": str(tmp_path)})
    worker.finished.connect(results.append, Qt.ConnectionType.DirectConnection)
    worker.run()
    grid = results[0]["grid"]
    assert array_storage(grid) == "disk" and _owner_folder(grid).parent == tmp_path


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


def test_one_time_choice_stays_with_the_action_that_accepted_it(app, window, monkeypatch):
    window._settings.setValue("datasets/result-storage-v1",
                              json.dumps({"mode": "memory", "ram_budget_bytes": 4096}))
    assert window._current_result_storage_options()["mode"] == "memory"

    class ContinueOnce:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.Accepted

        def options(self):
            return {"mode": "memory", "ram_budget_bytes": 4096, "allow_exceed": True}

        def deleteLater(self):
            pass

    monkeypatch.setattr(options_module, "ResultStorageDialog", ContinueOnce)
    monkeypatch.setattr(actions_module, "_derived_grid_memory_limit", lambda: 1)

    def start_job(owner):
        worker = _BackgroundCallableWorker(lambda: None)
        assert owner._try_start_background_job("Test job", worker)
        options = dict(worker._result_storage_options)
        deadline = time.monotonic() + 10
        while owner._background_job_active() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.005)
        app.processEvents()
        return options

    def accept_then_start(self):        # one action: review, then its own job
        assert self._review_result_ram_estimate("Regrid", 10**9)
        return start_job(self)

    def accept_then_stop(self):         # stops on a later check, like Regrid's metadata test
        assert self._review_result_ram_estimate("Regrid", 10**9)

    def unrelated_action(self):
        return start_job(self)

    assert accept_then_start(window).get("allow_exceed") is True
    accept_then_stop(window)
    assert not unrelated_action(window).get("allow_exceed")
