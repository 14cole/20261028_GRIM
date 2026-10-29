"""Inferred CSV frequency units are confirmed in the GUI; a choice can reload and persist."""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

import GRIM_Backend.ui.app as grim_cut_gui
from GRIM_Backend.ui.load_options import FrequencyUnitDialog
import test_gui_shell as shell


LEGACY = "azimuth,elevation,frequency,polarization,magnitude_linear\n0,0,500,VV,2\n10,0,500,VV,3\n"


class FrequencyUnitConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.patches = [
            mock.patch.object(grim_cut_gui, "GhostIntegrationWidget", shell._FakeGhostIntegration),
            mock.patch.object(grim_cut_gui, "load_ghost_module", return_value=shell._FakeFeatureWorkflow()),
            mock.patch.object(grim_cut_gui, "FreddyIntegrationWidget", shell._FakeFreddyIntegration),
        ]
        for patcher in self.patches:
            patcher.start()
        self.window = grim_cut_gui.GrimCutWindow(settings=shell._MemorySettings())
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.window.ghost_integration.running = False
        self.window.freddy_integration.running = False
        self.window.deleteLater()
        self.app.processEvents()
        for patcher in self.patches:
            patcher.stop()
        self.temp.cleanup()

    def _wait(self, timeout=20.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if not self.window._background_job_active() and not self.window._pending_import_batches:
                self.app.processEvents()
                return
            time.sleep(.005)
        raise AssertionError("import did not finish")

    def _legacy_file(self, name):
        path = Path(self.temp.name) / name
        path.write_text(LEGACY, encoding="utf-8")
        return str(path)

    def _row_dataset(self, row):
        return self.window.table.item(row, 0).data(Qt.UserRole)

    def test_keeping_the_inferred_unit_publishes_the_loaded_dataset(self):
        with mock.patch("GRIM_Backend.ui.load_options.FrequencyUnitDialog") as dialog_type:
            dialog = dialog_type.return_value
            dialog.exec.return_value = QDialog.Rejected
            self.window._handle_files_dropped([self._legacy_file("legacy.csv")])
            self._wait()
        dialog_type.assert_called_once()
        self.assertEqual(dialog_type.call_args.args[1], "GHz")
        self.assertEqual(self.window.table.rowCount(), 1)
        dataset = self._row_dataset(0)
        self.assertEqual(dataset.units["frequency"], "GHz")
        self.assertIs(dataset.extra["frequency_unit_inferred"], True)
        self.assertIn("inferred frequency unit GHz", self.window._last_import_summary)
        self.assertNotIn("declared_units", self.window.python_recorder.script)

    def test_choosing_a_unit_reloads_the_file_and_applies_to_the_session(self):
        with mock.patch("GRIM_Backend.ui.load_options.FrequencyUnitDialog") as dialog_type:
            dialog = dialog_type.return_value
            dialog.exec.return_value = QDialog.Accepted
            dialog.selected_unit.return_value = "MHz"
            dialog.apply_to_session.return_value = True
            self.window._handle_files_dropped([self._legacy_file("first.csv")])
            self._wait()
            self.assertEqual(dialog_type.call_count, 1)
            self.window._handle_files_dropped([self._legacy_file("second.csv")])
            self._wait()
        self.assertEqual(dialog_type.call_count, 1)
        self.assertEqual(self.window.table.rowCount(), 2)
        for row in range(2):
            dataset = self._row_dataset(row)
            self.assertEqual(dataset.units["frequency"], "MHz")
            self.assertIs(dataset.extra["frequency_unit_declared"], True)
            self.assertNotIn("frequency_unit_inferred", dataset.extra)
            self.assertIn("supplied by the user", dataset.history)
        self.assertIn("declared_units={'frequency': 'MHz'}", self.window.python_recorder.script)
        self.assertEqual(self.window._current_load_options().get("declared_units"), {"frequency": "MHz"})

    def test_dialog_defaults_to_the_inferred_unit_and_reports_choices(self):
        dialog = FrequencyUnitDialog("legacy.csv", "MHz", "median |frequency|=500")
        try:
            self.assertEqual(dialog.selected_unit(), "MHz")
            self.assertFalse(dialog.apply_to_session())
            dialog.unit_box.setCurrentText("Hz")
            dialog.remember.setChecked(True)
            self.assertEqual(dialog.selected_unit(), "Hz")
            self.assertTrue(dialog.apply_to_session())
        finally:
            dialog.deleteLater()
