"""Work finishing in the background must not lose results, requests or buttons."""
import os
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QDialog

import GRIM_Backend.ui.app as grim_app
import GRIM_Backend.ui.load_options as load_options_module
from GRIM_Backend.datasets.grid import RcsGrid
from test_gui_shell import (
    _FakeFeatureWorkflow, _FakeFreddyIntegration, _FakeGhostIntegration, _MemorySettings, _RecordingWindow,
)


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


def _quiet_steps(window, monkeypatch):
    monkeypatch.setattr(window, "_prompt_pending_table_mappings", lambda: None)
    monkeypatch.setattr(window, "_prompt_pending_unit_confirmations", lambda: None)
    monkeypatch.setattr(window, "_review_pending_load_memory", lambda: False)
    monkeypatch.setattr(window, "_start_next_pending_import_batch", lambda: False)


class _ChooseMHz:
    def __init__(self, *args, **kwargs):
        pass

    def exec(self):
        return QDialog.Accepted

    def selected_unit(self):
        return "MHz"

    def apply_to_session(self):
        return False

    def deleteLater(self):
        pass


def test_unit_reload_keeps_earlier_failures_of_the_cycle(window, monkeypatch, tmp_path):
    grid = RcsGrid([0.0], [0.0], [500.0], ["VV"], rcs_power=np.ones((1, 1, 1, 1)),
                   units={"frequency": "GHz"})
    grid.extra.update(frequency_unit_inferred=True, frequency_unit_inference="inferred for the test")
    window._pending_unit_confirmations = [
        {"dataset": grid, "path": str(tmp_path / "legacy.csv"), "load_options": {}}]
    window._import_cycle_results = [("Loaded 0 dataset(s). Failed: broken.csv (bad header)", True)]
    started = []
    monkeypatch.setattr(window, "_start_dataset_import_batch",
                        lambda paths, **kwargs: started.append((list(paths), kwargs)) or True)
    monkeypatch.setattr(load_options_module, "FrequencyUnitDialog", _ChooseMHz)

    window._prompt_pending_unit_confirmations()

    assert started and started[0][1]["load_options"]["declared_units"]["frequency"] == "MHz"
    assert any("broken.csv" in message and failed for message, failed in window._import_cycle_results)


def test_cycle_summary_waits_for_the_reload_and_reports_every_file(window, monkeypatch):
    _quiet_steps(window, monkeypatch)
    active = {"job": False}
    monkeypatch.setattr(window, "_background_job_active", lambda: active["job"])

    def reload_started():
        window._import_cycle_results.append(("Reloading legacy.csv with frequency unit MHz declared.", False))
        active["job"] = True

    monkeypatch.setattr(window, "_prompt_pending_unit_confirmations", reload_started)
    window._active_import_keys = {"first-batch"}
    window._import_cycle_results = [("Loaded 0 dataset(s). Failed: broken.csv (bad header)", True)]
    window._on_background_thread_finished()
    assert len(window._import_cycle_results) == 2      # not summarized while the reload runs

    active["job"] = False
    monkeypatch.setattr(window, "_prompt_pending_unit_confirmations", lambda: None)
    window._active_import_keys = {"legacy"}
    window._import_cycle_results.append(("Loaded 1 dataset(s).", False))
    window._on_background_thread_finished()
    assert window._last_import_summary.startswith("Dataset imports completed with errors.")
    assert "broken.csv" in window._last_import_summary
    assert window._import_cycle_results == []


def test_pending_isar_request_waits_for_the_dataset_job(window, monkeypatch):
    _quiet_steps(window, monkeypatch)
    submitted = []
    monkeypatch.setattr(window, "_isar_submit", submitted.append)
    active = {"job": True}
    monkeypatch.setattr(window, "_background_job_active", lambda: active["job"])
    window._isar_busy = False
    window._isar_pending = {"request": 1}

    window._on_background_thread_finished()
    assert submitted == [] and window._isar_pending == {"request": 1}

    active["job"] = False
    window._on_background_thread_finished()
    assert submitted == [{"request": 1}] and window._isar_pending is None


def test_a_failing_step_still_refreshes_buttons_and_drains_the_queue(window, monkeypatch):
    _quiet_steps(window, monkeypatch)
    calls = []

    def failing_step():
        raise RuntimeError("dialog exploded")

    monkeypatch.setattr(window, "_prompt_pending_unit_confirmations", failing_step)
    monkeypatch.setattr(window, "_update_dataset_action_states", lambda *a, **k: calls.append("buttons"))
    monkeypatch.setattr(window, "_start_next_pending_import_batch", lambda: calls.append("queue") or False)
    window._import_cycle_results = []

    window._on_background_thread_finished()

    assert calls == ["buttons", "queue"]
    assert any("dialog exploded" in message and failed for message, failed in window._import_cycle_results)
