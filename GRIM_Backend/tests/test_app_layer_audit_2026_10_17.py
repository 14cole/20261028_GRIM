"""Regressions for the 2026-10-17 application-layer audit (reports, UI, scripting)."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QApplication, QDialog, QDoubleSpinBox

import GRIM_Backend.ui.app as grim_cut_gui
import GRIM_Backend.ui.dataset_actions as dataset_actions
from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.transforms import crop_dataset
from GRIM_Backend.plotting.modes import az_vs_range_mode, isar_render
from GRIM_Backend.reports import report as rp
from GRIM_Backend.scripting import cli
from GRIM_Backend.scripting.recorder import _literal
from GRIM_Backend.ui.dataset_actions import DATASET_DIRTY_ROLE, DATASET_PATH_ROLE
from GRIM_Backend.ui.dataset_dialogs import PhaseCenterDialog, StatisticsDialog
from GRIM_Backend.ui.isar_controls import sync_frequency_controls
from test_gui_dataset_workflows import _axis_grid
from test_gui_shell import (
    _FakeFeatureWorkflow,
    _FakeFreddyIntegration,
    _FakeGhostIntegration,
    _MemorySettings,
    _RecordingWindow,
)


def _app():
    return QApplication.instance() or QApplication([])


@contextlib.contextmanager
def _captured_figure():
    """Yield a list of measurements taken from each report figure as it is saved.

    render_plot_png clears its figure after saving, so inspect it in place.
    """

    captured = []
    original = Figure.savefig

    def spy(self, *args, **kwargs):
        self.canvas.draw()
        axes = self.axes[0]
        renderer = self.canvas.get_renderer()
        ticks = {
            label.get_text(): label.get_window_extent(renderer)
            for label in axes.get_xticklabels()
        }
        captured.append(SimpleNamespace(
            xlim=tuple(axes.get_xlim()),
            markers=[line.get_marker() for line in axes.lines],
            ylabel_box=axes.yaxis.label.get_window_extent(renderer),
            tick_boxes=ticks,
        ))
        return original(self, *args, **kwargs)

    with mock.patch.object(Figure, "savefig", spy):
        yield captured


def _polar_spec(x, **kwargs):
    x = tuple(float(value) for value in x)
    y = tuple(-10.0 + 5.0 * np.cos(np.deg2rad(x)))
    return rp.PlotSpec(
        "p", "azimuth_polar", "t", "Azimuth (deg)", "RCS (dBsm)",
        (rp.PlotSeries(x, y, "A"),), y_limits=(-20.0, 0.0), **kwargs,
    )


class ReportRenderingTests(unittest.TestCase):
    def render(self, spec, width=300, height=300):
        with tempfile.TemporaryDirectory() as root, _captured_figure() as figures:
            rp.render_plot_png(spec, Path(root) / "p.png", width_points=width, height_points=height)
        return figures[-1]

    def test_polar_without_limits_shows_the_whole_circle(self):
        for x, expected in (
            (np.arange(0.0, 360.0, 10.0), (0.0, 360.0)),
            (np.arange(-180.0, 180.0, 10.0), (-180.0, 180.0)),
        ):
            with self.subTest(first=x[0]):
                shot = self.render(_polar_spec(x))
                np.testing.assert_allclose(np.rad2deg(shot.xlim), expected)

    def test_polar_radial_label_clears_the_minus_90_tick(self):
        for width in (300, 500):
            with self.subTest(width=width):
                shot = self.render(_polar_spec(np.arange(-180.0, 180.0, 10.0)), width, width)
                self.assertFalse(shot.ylabel_box.overlaps(shot.tick_boxes["-90°"]))

    def test_isolated_and_single_samples_get_markers(self):
        nan = float("nan")
        cases = (
            ((10.0,), (-5.0,), True),
            ((1.0, 2.0, 3.0, 4.0), (-5.0, nan, -6.0, nan), True),
            ((1.0, 2.0, 3.0), (-5.0, -6.0, nan), False),
        )
        for x, y, marked in cases:
            with self.subTest(y=y):
                spec = rp.PlotSpec(
                    "f", "frequency", "t", "F", "RCS",
                    (rp.PlotSeries(x, y, "A"),), y_limits=(-20.0, 0.0),
                )
                marker = self.render(spec, 500, 300).markers[0]
                self.assertEqual(marker not in (None, "None", ""), marked)


class ReportClippingWarningTests(unittest.TestCase):
    def test_polar_0_360_data_is_not_clipped_by_signed_limits(self):
        _app()
        from GRIM_Backend.reports.workspace import PptWorkspace

        spec = _polar_spec(np.arange(0.0, 360.0, 10.0))
        warnings = PptWorkspace._axis_clipping_warnings(
            (spec,), x_limits=(-180.0, 180.0), x_step=45.0,
            y_limits=(-20.0, 0.0), y_step=5.0,
        )
        self.assertFalse([w for w in warnings if "horizontal-axis" in w], warnings)
        # A genuinely narrower polar sector still reports clipping.
        warnings = PptWorkspace._axis_clipping_warnings(
            (spec,), x_limits=(-90.0, 90.0), x_step=45.0,
            y_limits=(-20.0, 0.0), y_step=5.0,
        )
        self.assertTrue([w for w in warnings if "horizontal-axis" in w])


class IsarBandToleranceTests(unittest.TestCase):
    def test_full_band_default_keeps_both_endpoint_frequencies(self):
        _app()
        frequencies = np.linspace(8.0, 12.333333333333334, 14)
        context = SimpleNamespace(
            spin_isar_freq_min=QDoubleSpinBox(), spin_isar_freq_max=QDoubleSpinBox()
        )
        sync_frequency_controls(
            context, SimpleNamespace(frequencies=frequencies, units={"frequency": "GHz"})
        )
        lo = context.spin_isar_freq_min.value()
        hi = context.spin_isar_freq_max.value()
        self.assertLess(hi, frequencies[-1])  # the spin really rounds the bound
        for module in (isar_render, az_vs_range_mode):
            with self.subTest(module=module.__name__):
                low, high = module._spin_band_bounds(
                    context.spin_isar_freq_min, context.spin_isar_freq_max, lo, hi
                )
                self.assertEqual(int(np.sum((frequencies >= low) & (frequencies <= high))), 14)

    def test_interior_band_uses_half_display_step(self):
        _app()
        spin_lo, spin_hi = QDoubleSpinBox(), QDoubleSpinBox()
        for spin in (spin_lo, spin_hi):
            spin.setDecimals(3)
            spin.setRange(0.0, 100.0)
        low, high = isar_render._spin_band_bounds(spin_lo, spin_hi, 9.0, 11.0)
        self.assertAlmostEqual(low, 8.9995)
        self.assertAlmostEqual(high, 11.0005)
        self.assertFalse(low <= 8.998)


class RecorderCompactionTests(unittest.TestCase):
    def assert_replays_identically(self, value):
        literal = _literal(value)
        replayed = eval(literal, {"np": np})
        self.assertIs(type(replayed), type(value), literal)
        if isinstance(value, np.ndarray):
            self.assertEqual(replayed.dtype, value.dtype, literal)
            np.testing.assert_array_equal(replayed, value)
        else:
            self.assertEqual(replayed, value)
            self.assertEqual([type(item) for item in replayed], [type(item) for item in value])
        return literal

    def test_compacted_sequences_keep_container_and_number_types(self):
        self.assertIn("tolist()", self.assert_replays_identically([float(v) for v in range(300)]))
        self.assertIn("np.arange", self.assert_replays_identically(list(range(5, 305, 3))))
        self.assertIn("np.arange", self.assert_replays_identically(np.arange(40)))
        self.assertIn("np.arange", self.assert_replays_identically(np.arange(40, dtype=np.int32)))
        self.assertIn("np.linspace", self.assert_replays_identically(np.linspace(0.0, 1.0, 50)))
        # Mixed int/float lists are not compacted (they would all become floats).
        self.assertNotIn("np.", _literal([0, 1.0] + list(range(2, 30))))

    def test_long_crop_selection_replays_with_identical_history(self):
        count = 300
        power = np.ones((count, 1, 2, 1))
        grid = RcsGrid(
            np.arange(count, dtype=float), np.asarray([0.0]), np.asarray([9.0, 10.0]),
            np.asarray(["HH"]), rcs_power=power, rcs_phase=np.zeros_like(power),
            rcs_domain="power_phase", units={"frequency": "GHz", "rcs_log_unit": "dBsm"},
        )
        selection = grid.azimuths[: count - 1].tolist()
        replayed = eval(_literal(selection), {"np": np})
        self.assertEqual(
            crop_dataset(grid, azimuths=selection).history,
            crop_dataset(grid, azimuths=replayed).history,
        )


class DialogPrecisionTests(unittest.TestCase):
    def test_precision_of_phase_center_and_percentile_spins(self):
        _app()
        phase = PhaseCenterDialog()
        stats = StatisticsDialog()
        try:
            self.assertTrue(all(spin.decimals() >= 7 for spin in phase.spins))
            self.assertGreaterEqual(stats.spin_pct.decimals(), 3)
        finally:
            phase.deleteLater()
            stats.deleteLater()


class CliValidationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        power = np.ones((2, 1, 2, 1))
        grid = RcsGrid(
            np.asarray([0.0, 10.0]), np.asarray([0.0]), np.asarray([9.0, 10.0]),
            np.asarray(["HH"]), rcs_power=power, rcs_phase=np.zeros_like(power),
            rcs_domain="power_phase", units={"frequency": "GHz", "rcs_log_unit": "dBsm"},
        )
        self.input = str(grid.save(str(self.root / "a.grim")))

    def tearDown(self):
        self._tmp.cleanup()

    def fails(self, argv, message):
        stderr = io.StringIO()
        with mock.patch.object(cli, "combine_datasets") as combine, \
                contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as caught:
                cli.main(argv)
        self.assertEqual(caught.exception.code, 2)
        self.assertIn(message, stderr.getvalue())
        combine.assert_not_called()

    def test_usage_errors_are_reported_before_any_combination(self):
        self.fails([self.input], "--output is required")
        self.fails([self.input, "-o", str(self.root / "missing" / "o.grim")], "folder does not exist")
        self.fails([self.input, "-o", self.input], "must not overwrite")
        self.fails([self.input, "--folder", str(self.root), "-o", "o.grim"], "not both")
        self.fails(["--folder", str(self.root / "nope"), "-o", "o.grim"], "does not exist")
        empty = self.root / "empty"
        empty.mkdir()
        self.fails(["--folder", str(empty), "-o", str(self.root / "o.grim")], "no supported datasets")
        self.fails([str(self.root / "missing.grim"), "-o", str(self.root / "o.grim")], "not found")
        self.fails([self.input, "--stitch-policy", "bogus", "-o", str(self.root / "o.grim")],
                   "invalid choice")

    def test_stitch_policy_accepts_underscore_spelling(self):
        args = cli._parser().parse_args([self.input, "--stitch-policy", "Power_Mean"])
        self.assertEqual(args.stitch_policy, "power-mean")


class GuiEditAndRecordingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _app()

    def setUp(self):
        self.patches = [
            mock.patch.object(grim_cut_gui, "GhostIntegrationWidget", _FakeGhostIntegration),
            mock.patch.object(grim_cut_gui, "load_ghost_module", return_value=_FakeFeatureWorkflow()),
            mock.patch.object(grim_cut_gui, "FreddyIntegrationWidget", _FakeFreddyIntegration),
        ]
        for patch in self.patches:
            patch.start()
        self.window = _RecordingWindow(settings=_MemorySettings())
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self.window.ghost_integration.running = False
        self.window.freddy_integration.running = False
        self.window.deleteLater()
        self.app.processEvents()
        for patch in reversed(self.patches):
            patch.stop()
        self._tmp.cleanup()

    def add_saved_row(self):
        source = _axis_grid([0.0, 1.0, 2.0], 1.0)
        path = str(self.root / "s.grim")
        source.save(path)
        self.window._add_dataset_row(source, "A", "Loaded", path)
        self.window.table.selectRow(0)
        self.app.processEvents()
        row_dataset = self.window.table.item(0, 0).data(Qt.UserRole)
        self.window.active_dataset = row_dataset
        self.window._populate_params(row_dataset)
        return path

    def test_inline_edit_clears_durable_source_path(self):
        path = self.add_saved_row()
        # setText emits itemChanged, which commits through _on_param_item_changed.
        self.window.list_az.item(1).setText("1.5")
        self.app.processEvents()
        self.assertEqual(
            self.window.table.item(0, 0).data(Qt.UserRole).azimuths.tolist(), [0.0, 1.5, 2.0]
        )
        file_item = self.window.table.item(0, 1)
        self.assertEqual(file_item.text(), "Unsaved")
        self.assertEqual(file_item.data(DATASET_PATH_ROLE) or "", "")
        self.assertIn(path, file_item.toolTip())
        self.assertTrue(self.window.table.item(0, 0).data(DATASET_DIRTY_ROLE))
        edited = self.window.table.item(0, 0).data(Qt.UserRole)
        self.window.python_recorder.clear()
        reference = self.window._python_reference_for_dataset(edited)
        self.assertEqual(reference.path, "")

    def test_edit_during_background_job_is_rejected_and_replay_matches(self):
        self.add_saved_row()
        window = self.window
        release, started = threading.Event(), threading.Event()
        real_shift = dataset_actions.shift_dataset

        def slow_shift(dataset, **kwargs):
            started.set()
            release.wait(5)
            return real_shift(dataset, **kwargs)

        with mock.patch.object(dataset_actions, "shift_dataset", slow_shift), \
                mock.patch.object(dataset_actions, "ShiftDialog") as dialog_type:
            dialog_type.return_value.exec.return_value = QDialog.Accepted
            dialog_type.return_value.get_params.return_value = {
                "azimuth": (True, 10.0), "elevation": (False, 0.0), "phase": (False, 0.0),
            }
            window._shift_selected()
            self.assertTrue(started.wait(5))
            self.app.processEvents()
            self.assertTrue(window._background_job_active())
            for widget in (window.list_az, window.list_freq, window.table):
                self.assertEqual(widget.editTriggers(), QAbstractItemView.NoEditTriggers)
            item = window.list_az.item(2)
            item.setText("5.0")  # emits itemChanged -> _on_param_item_changed
            self.app.processEvents()
            self.assertIn("running dataset job", window.status.currentMessage())
            self.assertEqual(float(window.list_az.item(2).text()), 2.0)
            release.set()
            deadline = time.monotonic() + 10
            while window._background_job_active() and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.01)
            self.app.processEvents()
        self.assertNotEqual(window.list_az.editTriggers(), QAbstractItemView.NoEditTriggers)
        self.assertNotEqual(window.table.editTriggers(), QAbstractItemView.NoEditTriggers)
        self.assertNotIn("edit_axis_value", window.python_recorder.script)
        gui = window.table.item(window.table.rowCount() - 1, 0).data(Qt.UserRole)
        namespace = {"__name__": "replay", "__file__": str(self.root / "replay.py")}
        exec(compile(window.python_recorder.script, "<replay>", "exec"), namespace)
        replayed = [value for value in namespace.values() if isinstance(value, RcsGrid)]
        np.testing.assert_array_equal(replayed[-1].azimuths, gui.azimuths)


if __name__ == "__main__":
    unittest.main()
