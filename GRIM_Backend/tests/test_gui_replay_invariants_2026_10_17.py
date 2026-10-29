"""A recorded multi-operation GUI session replays to bit-identical datasets.

Every output row created through the dataset buttons is compared with the
dataset the generated Python script produces: samples (bit for bit), storage
kind/domain, dtype, axes, units, and every extra tag except the per-execution
operation provenance record (it carries fresh UUIDs and timestamps).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QApplication, QDialog

import GRIM_Backend.ui.app as grim_cut_gui
from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.operations import OPERATION_PROVENANCE_KEY
from GRIM_Backend.ui.dataset_actions import DATASET_ID_ROLE
from test_gui_shell import (
    _FakeFeatureWorkflow,
    _FakeFreddyIntegration,
    _FakeGhostIntegration,
    _RecordingWindow,
)

AZ = np.asarray([0.0, 10.0, 20.0, 30.0])
EL = np.asarray([0.0, 5.0])
FR = np.asarray([8.0, 9.0, 10.0])
POL = ["HH", "VV"]
SHAPE = (4, 2, 3, 2)
UNITS = {"azimuth": "deg", "elevation": "deg", "frequency": "GHz",
         "rcs_linear_quantity": "sigma_3d", "rcs_log_unit": "dBsm"}


def _field(seed, dtype=np.complex128):
    rng = np.random.default_rng(seed)
    field = (rng.normal(size=SHAPE) + 1j * rng.normal(size=SHAPE)).astype(dtype)
    field[0, 0, 0, 0] = 0
    return field


def _fixtures():
    power = np.abs(_field(4)) ** 2
    phase = np.angle(_field(4))
    phase[1, 0, 1, 0] = np.nan  # unknown phase -> power_phase storage
    return {
        "complex64": RcsGrid(AZ, EL, FR, POL, rcs=_field(1, np.complex64), units=dict(UNITS)),
        "complex128": RcsGrid(AZ, EL, FR, POL, rcs=_field(2), units=dict(UNITS)),
        # A legacy GHOST delta archive as the native loader converts it.
        "delta": RcsGrid._from_native_arrays(dict(
            azimuths=np.asarray(AZ, float), elevations=np.asarray(EL, float),
            frequencies=np.asarray(FR, float), polarizations=np.asarray(POL),
            units=__import__("json").dumps(UNITS), grim_format_version=np.int16(2),
            storage_kind="complex", storage_domain="raw_field", rcs_complex=_field(3),
            power_domain="delta_amp_sq", rcs_domain="delta", source_path="", history=""),
            path="legacy delta"),
        "power_phase": RcsGrid(AZ, EL, FR, POL, rcs_power=power, rcs_phase=phase,
                               units=dict(UNITS, phase_wrap="-180_180")),
        "power": RcsGrid(AZ, EL, FR, POL, rcs_power=np.abs(_field(5)) ** 2, units=dict(UNITS)),
        "raw2d": RcsGrid(AZ, EL, FR, POL, rcs=_field(6), rcs_storage_domain="raw_field",
                         units=dict(UNITS, rcs_linear_quantity="sigma_2d", rcs_log_unit="dBke")),
    }


def assert_bit_identical(case, gui, replay, label):
    case.assertEqual(gui.storage_kind, replay.storage_kind, label)
    case.assertEqual(gui.storage_domain, replay.storage_domain, label)
    case.assertEqual(gui.real_dtype, replay.real_dtype, label)
    for name in ("azimuths", "elevations", "frequencies", "polarizations"):
        left, right = getattr(gui, name), getattr(replay, name)
        case.assertEqual(left.dtype, right.dtype, f"{label}: {name} dtype")
        np.testing.assert_array_equal(left, right, err_msg=f"{label}: {name}")
    case.assertEqual(gui.units, replay.units, label)
    left, right = gui.native_sample_payload(), replay.native_sample_payload()
    case.assertEqual(set(left), set(right), label)
    for key, value in left.items():
        if isinstance(value, np.ndarray):
            case.assertEqual(value.dtype, right[key].dtype, f"{label}: {key}")
            case.assertTrue(np.array_equal(value, right[key], equal_nan=True),
                            f"{label}: {key} samples differ")
        else:
            case.assertEqual(value, right[key], f"{label}: {key}")
    keys = set(gui.extra) - {OPERATION_PROVENANCE_KEY}
    case.assertEqual(keys, set(replay.extra) - {OPERATION_PROVENANCE_KEY}, label)
    for key in keys:
        left, right = np.asarray(gui.extra[key]), np.asarray(replay.extra[key])
        case.assertTrue(left.dtype == right.dtype and np.array_equal(
            left, right, equal_nan=left.dtype.kind in "fc"), f"{label}: extra {key}")
    # Lineage is recorded for both, naming the same operation sequence.
    def operations(grid):
        text = np.asarray(grid.extra.get(OPERATION_PROVENANCE_KEY, '{"events": []}')).item()
        return [event["operation"] for event in json.loads(text)["events"]]
    case.assertEqual(operations(gui), operations(replay), label)


class RecordedSessionReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        patches = (
            mock.patch.object(grim_cut_gui, "GhostIntegrationWidget", _FakeGhostIntegration),
            mock.patch.object(grim_cut_gui, "load_ghost_module", return_value=_FakeFeatureWorkflow()),
            mock.patch.object(grim_cut_gui, "FreddyIntegrationWidget", _FakeFreddyIntegration),
        )
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.window = _RecordingWindow()
        self.folder = tempfile.TemporaryDirectory(prefix="grim-replay-")
        self.addCleanup(self.folder.cleanup)

    def tearDown(self):
        self.window.ghost_integration.running = False
        self.window.freddy_integration.running = False
        self.window.deleteLater()
        self.app.processEvents()

    def _select(self, *rows):
        table = self.window.table
        table.clearSelection()
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        for row in rows:
            table.setCurrentCell(row, 0, QItemSelectionModel.SelectionFlag.NoUpdate)
            table.selectionModel().select(table.model().index(row, 0), flags)
            self.app.processEvents()

    def _wait(self, timeout=10.0):
        deadline = time.monotonic() + timeout
        while self.window._background_job_active() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.app.processEvents()
        self.assertFalse(self.window._background_job_active())

    def _run(self, rows, button, **patches):
        before = self.window.table.rowCount()
        self._select(*rows)
        managers = [mock.patch(f"GRIM_Backend.ui.dataset_actions.{name}", value)
                    for name, value in patches.items()]
        for manager in managers:
            manager.start()
        try:
            getattr(self.window, button).click()
            self._wait()
        finally:
            for manager in managers:
                manager.stop()
        created = list(range(before, self.window.table.rowCount()))
        self.assertTrue(created, f"{button} created no dataset: {self.window.status.currentMessage()}")
        return created

    @staticmethod
    def _dialog(**methods):
        dialog_type = mock.MagicMock()
        dialog = dialog_type.return_value
        dialog.exec.return_value = QDialog.Accepted
        for name, value in methods.items():
            getattr(dialog, name).return_value = value
        return dialog_type

    def test_recorded_session_replays_bit_identically(self):
        rows = {}
        for name, dataset in _fixtures().items():
            path = str(Path(self.folder.name) / f"{name}.grim")
            dataset.save(path)
            rows[name] = self.window.table.rowCount()
            self.window._add_dataset_row(RcsGrid.load(path), name, "Loaded", path)

        outputs = []
        outputs += self._run([rows["delta"], rows["complex64"], rows["raw2d"]], "btn_flip_phase")
        flipped_delta = outputs[0]
        restored_delta = self._run([flipped_delta], "btn_flip_phase")
        outputs += restored_delta
        outputs += self._run([rows["power_phase"], rows["delta"]], "btn_offset",
                             **{"QInputDialog.getDouble": mock.Mock(return_value=(3.25, True))})
        outputs += self._run([rows["complex64"], rows["power_phase"], rows["delta"]], "btn_shift",
                             ShiftDialog=self._dialog(get_params={
                                 "azimuth": (True, 5.0), "elevation": (False, 0.0),
                                 "phase": (True, 33.0)}))
        outputs += self._run([rows["complex64"], rows["complex128"]], "btn_coherent_sub")
        outputs += self._run([rows["power_phase"], rows["power"]], "btn_incoherent_add")
        outputs += self._run([rows["power_phase"], rows["delta"]], "btn_wrap",
                             WrapDialog=self._dialog(get_params={
                                 "azimuth": False, "phase": True, "mode": "0_360"}))
        outputs += self._run([rows["complex128"], rows["delta"]], "btn_extrusion",
                             ExtrusionConversionDialog=self._dialog(
                                 destination="dbke", length_m=1.5, display_text="1.5 m"))
        outputs += self._run([rows["complex64"], rows["delta"]], "btn_decimate",
                             DecimateDialog=self._dialog(get_params={
                                 "axis": "azimuth", "factor": 2, "mode": "coherent",
                                 "partial": "keep"}))
        outputs += self._run([rows["power_phase"], rows["complex64"]], "btn_stats",
                             StatisticsDialog=self._dialog(
                                 get_params=("mean", 50.0, ["azimuth"], True)))
        outputs += self._run([rows["delta"], rows["power_phase"]], "btn_phase_center",
                             PhaseCenterDialog=self._dialog(get_params={
                                 "x_m": 0.25, "y_m": -0.1, "z_m": 0.0,
                                 "entered": (0.25, -0.1, 0.0), "unit": "m"}))
        outputs += self._run([rows["delta"], restored_delta[0]], "btn_join",
                             JoinDialog=self._dialog(get_params={"policy": "error", "tol": 1e-6}))

        outputs += self._run([rows["complex64"], rows["delta"], rows["power_phase"]], "btn_slice",
                             CropDialog=self._dialog(get_params={
                                 "mode": "ranges",
                                 "ranges": {"azimuth": (10.0, 30.0), "elevation": None,
                                            "frequency": (8.0, 9.0)},
                                 "strides": {"azimuth": 2, "elevation": 1, "frequency": 1},
                                 "selected_polarizations": False}))
        regridded = self._run([rows["complex128"], rows["delta"], rows["raw2d"]], "btn_interpolate",
                             RegridDialog=self._dialog(get_params={
                                 "axis": "frequency", "start": 8.0, "stop": 10.0, "step": 0.25,
                                 "unit": "GHz", "max_gap": None, "support": "interpolate"}))
        outputs += regridded
        outputs += self._run([rows["delta"], rows["raw2d"], rows["power"]], "btn_axis_units",
                             AxisUnitsDialog=self._dialog(get_params={
                                 "azimuth": "rad", "elevation": "deg", "frequency": "MHz"}))
        outputs += self._run([rows["delta"], rows["power_phase"]], "btn_mirror",
                             **{"QInputDialog.getDouble": mock.Mock(return_value=(15.0, True))})
        outputs += self._run([rows["delta"], rows["complex64"]], "btn_swap_el_az")
        outputs += self._run([rows["delta"], rows["power_phase"]], "btn_round",
                             RoundDialog=self._dialog(get_params={
                                 "azimuths": True, "elevations": True, "frequencies": True,
                                 "decimals": 3}))
        outputs += self._run([rows["delta"], rows["power_phase"]], "btn_duplicate")
        outputs += self._run([rows["complex64"], rows["delta"]], "btn_coherent_add")
        outputs += self._run([rows["complex128"], rows["delta"]], "btn_coherent_div")
        outputs += self._run([rows["delta"], rows["power"]], "btn_medianize",
                             MedianizeDialog=self._dialog(get_params={
                                 "window_deg": 20.0, "slide_deg": 10.0}))
        outputs += self._run(regridded, "btn_time_gate",
                             TimeGateDialog=self._dialog(get_params={
                                 "start_m": -0.2, "stop_m": 0.2, "taper": 0.2,
                                 "mode": "keep", "compensate": True}))

        recorder = self.window.python_recorder
        namespace = {"__name__": "__grim_replay__", "__file__": __file__}
        exec(compile(recorder.script, "<session replay>", "exec"), namespace)
        for row in outputs:
            item = self.window.table.item(row, 0)
            variable = recorder._dataset_vars.get(str(item.data(DATASET_ID_ROLE)))
            self.assertIsNotNone(variable, f"{item.text()} was not recorded")
            assert_bit_identical(self, item.data(Qt.UserRole), namespace[variable], item.text())


if __name__ == "__main__":
    unittest.main()
