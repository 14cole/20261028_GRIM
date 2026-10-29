"""Closing GRIM while background work runs must not crash the process."""
import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

import GRIM_Backend.ui.app as grim_app
from test_gui_shell import (
    _FakeFeatureWorkflow, _FakeFreddyIntegration, _FakeGhostIntegration, _MemorySettings, _RecordingWindow,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _start_pool_job(seconds):
    finished = threading.Event()

    def work():
        time.sleep(seconds)
        finished.set()

    QThreadPool.globalInstance().start(work)
    return finished


def test_drain_waits_for_pooled_jobs(app):
    finished = _start_pool_job(0.3)
    assert grim_app.drain_background_work(timeout_ms=10_000)
    assert finished.is_set()


def test_shutdown_drain_runs_when_the_application_quits(app):
    grim_app.install_shutdown_drain(app)
    finished = _start_pool_job(0.3)
    app.aboutToQuit.emit()
    assert finished.is_set()


_EXIT_SCRIPT = textwrap.dedent("""
    import sys, time
    sys.path.insert(0, {root!r})
    from PySide6.QtCore import QThreadPool, QTimer
    from PySide6.QtWidgets import QApplication, QMainWindow
    from GRIM_Backend.datasets.result_storage import allocate_result, operation_result_storage
    import GRIM_Backend.ui.app as grim_app

    app = QApplication(sys.argv)
    grim_app.install_shutdown_drain(app)
    window = QMainWindow()
    with operation_result_storage("disk", cache_dir={cache!r}):
        values = allocate_result((2_000_000,), "f8", fill=1.0)

    def work(samples=values):
        for _ in range(12):          # still reading the mapped buffer after close
            float(samples.sum())
            time.sleep(0.1)

    QThreadPool.globalInstance().start(work)
    del values
    window.show()
    QTimer.singleShot(200, window.close)
    sys.exit(app.exec())
""")


def test_exit_while_a_pool_job_reads_a_disk_backed_buffer_is_clean(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    script = tmp_path / "exit_with_job.py"
    script.write_text(_EXIT_SCRIPT.format(root=str(PROJECT_ROOT), cache=str(cache)), encoding="utf-8")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                          timeout=120, env=env, cwd=str(tmp_path))
    assert proc.returncode == 0, (proc.returncode, proc.stderr[-2000:])
    assert not list(cache.glob("grim-result-*"))


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
        inspector = getattr(win.assembly_workspace, "interference_inspector", None)
        if inspector is not None:
            inspector._thread = None
        win.ghost_integration.running = False
        win.freddy_integration.running = False
        win.deleteLater()
        app.processEvents()
        for patch in reversed(patches):
            patch.stop()


def test_close_is_refused_while_interference_metrics_run(window):
    inspector = window.assembly_workspace.interference_inspector
    inspector._cancel.clear()
    inspector._thread = object()          # stands in for the running QThread
    assert window.close() is False
    assert inspector._cancel.is_set()
    assert "interference" in window.status.currentMessage().lower()
    inspector._thread = None
    assert window.close() is True
