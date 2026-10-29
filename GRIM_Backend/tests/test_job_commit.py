"""A cancel request must not report "nothing published" after files were written."""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QApplication

from GRIM_Backend.execution.dataset_jobs import _BackgroundCallableWorker, mark_job_committed


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _run_with_cancel(app, function, *, reports_progress):
    """Run ``function`` in a worker thread and request Cancel while it runs."""
    thread = QThread()
    worker = _BackgroundCallableWorker(function, reports_progress=reports_progress)
    worker.moveToThread(thread)
    payloads = []
    worker.finished.connect(payloads.append, Qt.ConnectionType.DirectConnection)
    thread.started.connect(worker.run)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not payloads and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.005)
    finally:
        thread.quit()
        thread.wait(5000)
    assert payloads, "the worker never reported"
    return payloads[0]


def _cancel_current_job():
    QThread.currentThread().requestInterruption()


def test_published_work_is_reported_even_if_cancel_arrives(app, tmp_path):
    target = tmp_path / "published.pio"

    def export(progress):
        progress(0, 1, "Writing")
        target.write_text("samples")          # the file is now published
        _cancel_current_job()                 # the user presses Cancel too late
        mark_job_committed()
        progress(1, 1, "Published")           # must not raise after the commit
        return str(target)

    payload = _run_with_cancel(app, export, reports_progress=True)
    assert payload["ok"] is True and payload["result"] == str(target)
    assert payload["cancel_ignored"] is True


def test_unpublished_work_is_still_cancelled(app):
    def compute(progress):
        progress(0, 1, "Computing")
        _cancel_current_job()
        return "result nobody should publish"

    payload = _run_with_cancel(app, compute, reports_progress=True)
    assert payload == {"ok": False, "cancelled": True}


def test_commit_outside_a_job_is_harmless():
    mark_job_committed()


def test_window_reports_kept_results_after_a_late_cancel(app):
    from types import SimpleNamespace
    from GRIM_Backend.ui.dataset_actions import DatasetOpsMixin

    messages = []
    status = SimpleNamespace(showMessage=messages.append,
                             currentMessage=lambda: messages[-1] if messages else "")
    owner = SimpleNamespace(status=status, _background_worker_name="Pioneer export")
    owner._pending_callable_completion = lambda saved: status.showMessage(f"Exported {saved}.")
    DatasetOpsMixin._on_background_callable_finished(
        owner, {"ok": True, "result": "cut.pio", "cancel_ignored": True})
    assert messages[-1].startswith("Exported cut.pio.")
    assert "kept" in messages[-1]
