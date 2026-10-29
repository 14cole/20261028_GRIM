"""Bounded statistics values, coordinates, GUI publication, and recording."""
import json
import unittest
from unittest import mock

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.statistics_bands import band_statistics_dataset
from GRIM_Backend.ui.dataset_dialogs import PercentileDialog
from GRIM_Backend.ui.sector_statistics_dialog import SectorStatisticsDialog
from GRIM_Backend.plotting.modes.common import parse_sectors
from GRIM_Backend.plotting.modes.sector_stats_mode import _sector_linear_statistics
import test_gui_shell as shell


def source():
    return RcsGrid([-10., 0., 10., 20.], [-5., 5.], [8., 9., 10., 11.], ['VV', 'HH'],
                   rcs_power=np.arange(64., dtype=float).reshape(4, 2, 4, 2),
                   units={'azimuth': 'deg', 'elevation': 'deg', 'frequency': 'GHz'})


class BandStatisticsTests(unittest.TestCase):
    def test_joint_percentile_and_defined_bounds_preserve_other_axes(self):
        original = source()
        result = band_statistics_dataset(original, azimuth_band=[-11, 1], frequency_band=[8.5e9, 10.5e9],
                                         axes=['azimuth', 'frequency'], percentile=50)
        selected = original.power[:2, :, 1:3, :]
        expected = np.percentile(selected, 50, axis=(0, 2), keepdims=True, method='inverted_cdf')
        np.testing.assert_allclose(result.power, np.broadcast_to(expected, selected.shape))
        np.testing.assert_array_equal(result.azimuths, [-10, 0])
        np.testing.assert_array_equal(result.frequencies, [9, 10])
        np.testing.assert_array_equal(result.elevations, original.elevations)
        self.assertTrue(np.isnan(result.phase).all())
        self.assertFalse(np.shares_memory(result.power, original.power))
        self.assertEqual(json.loads(result.extra['statistics_bands_json'])['azimuth_bounds_deg'], [-11, 1])

    def test_frequency_only_interpolation_and_native_units(self):
        original = source().convert_axis_units(azimuth='rad', frequency='Hz')
        result = band_statistics_dataset(original, frequency_band=[8e9, 9e9], axes=['frequency'],
                                         percentile=75, interpolate=True)
        selected = original.power[:, :, :2, :]
        expected = np.percentile(selected, 75, axis=2, keepdims=True, method='linear')
        np.testing.assert_allclose(result.power, np.broadcast_to(expected, selected.shape))
        np.testing.assert_array_equal(result.azimuths, original.azimuths)
        np.testing.assert_array_equal(result.frequencies, [8e9, 9e9])
        wrapped = band_statistics_dataset(original, azimuth_band=[350, 10], percentile=50)
        np.testing.assert_allclose(np.rad2deg(wrapped.azimuths), [-10, 0, 10])

    def test_sector_outputs_match_plot_membership_and_statistics(self):
        original = RcsGrid([-180., -170., -10., 0., 10., 170., 180.], [0], [9], ['VV'],
                           rcs_power=np.array([1., 2., 0., np.nan, 9., 10., 11.]).reshape(7, 1, 1, 1))
        for text in ('170:-170, -10:10', '-180:90:180'):
            for sector in parse_sectors(text, original.azimuths):
                members = sector.contains(original.azimuths)
                if not members.any():
                    continue
                for statistic in ('mean', 'median', 'min', 'max', 'percentile'):
                    result = band_statistics_dataset(
                        original, statistic=statistic, percentile=60,
                        azimuth_band=[sector.start, sector.start + sector.width],
                        azimuth_modular=sector.modular, azimuth_closed=sector.closed)
                    np.testing.assert_array_equal(result.azimuths, original.azimuths[members])
                    expected = _sector_linear_statistics(original.power[:, 0, 0, 0], members, 60)[statistic]
                    np.testing.assert_allclose(result.power, expected)

    def test_missing_band_and_no_matching_selection_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, 'No samples'):
            band_statistics_dataset(source(), frequency_band=[20e9, 21e9])
        with self.assertRaisesRegex(ValueError, 'No matching'):
            band_statistics_dataset(source(), selection={'polarizations': []})
        with self.assertRaisesRegex(ValueError, 'increasing'):
            band_statistics_dataset(source(), frequency_band=[10e9, 9e9])

    def test_unknown_cells_stay_unknown_and_zero_counts_in_percentiles(self):
        original = source()
        original = RcsGrid(original.azimuths, original.elevations, original.frequencies,
                           original.polarizations, rcs_power=np.full(original.shape, np.nan), units=original.units)
        result = band_statistics_dataset(original, axes=['azimuth', 'frequency'])
        self.assertTrue(np.isnan(result.power).all())
        power = np.full(original.shape, np.nan)
        power[0] = 0.
        original = RcsGrid(original.azimuths, original.elevations, original.frequencies,
                           original.polarizations, rcs_power=power, units=original.units)
        result = band_statistics_dataset(original, axes=['azimuth', 'frequency'])
        np.testing.assert_array_equal(result.power, np.zeros(result.shape))

    def test_python_recording_replays_physical_bounds(self):
        from GRIM_Backend.scripting.recorder import PythonScriptRecorder, DatasetReference
        original = source()
        recorder = PythonScriptRecorder()
        kwargs = dict(azimuth_band=[-10, 0], frequency_band=[8e9, 9e9],
                      axes=['azimuth', 'frequency'], percentile=75, interpolate=True)
        recorder.record_function(DatasetReference('output', 'Output'), 'band_statistics_dataset',
                                 [DatasetReference('source', 'Source', 'source.grim')], kwargs=kwargs)
        namespace = {'__file__': __file__}
        with mock.patch('GRIM_Backend.scripting.api.load_dataset', return_value=original):
            exec(recorder.script, namespace)
        expected = band_statistics_dataset(original, **kwargs)
        np.testing.assert_allclose(namespace['dataset_2'].power, expected.power)


class BandStatisticsGuiTests(unittest.TestCase):
    setUp = shell.UnifiedGuiShellTest.setUp
    tearDown = shell.UnifiedGuiShellTest.tearDown
    _wait_for_background = shell.UnifiedGuiShellTest._wait_for_background

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def add_source(self):
        w = self.window
        w._add_dataset_row(source(), 'Example', 'Synthetic', '')
        w.table.selectRow(0)
        for listing in (w.list_az, w.list_elev, w.list_freq, w.list_pol):
            listing.selectAll()
        return w

    def test_gui_creates_cartesian_band_results_and_records_bounded_action(self):
        w = self.add_source()
        dialog = PercentileDialog(w)
        self.addCleanup(dialog.deleteLater)
        dialog.azimuth_bands.add_band(-10, 0)
        dialog.azimuth_bands.add_band(10, 20)
        dialog.frequency_bands.setChecked(True)
        dialog.frequency_bands.add_band(8, 9)
        dialog.frequency_bands.add_band(10, 11)
        with mock.patch('GRIM_Backend.ui.dataset_actions.PercentileDialog', return_value=dialog), mock.patch.object(dialog, 'exec', return_value=QDialog.Accepted):
            w.btn_percentile.click()
            self._wait_for_background()
        self.assertEqual(w.table.rowCount(), 5, w.status.currentMessage())
        for row in range(1, 5):
            result = w.table.item(row, 0).data(Qt.UserRole)
            self.assertEqual(result.shape, (2, 2, 2, 2))
            self.assertIn('statistics_bands_json', result.extra)
        self.assertIn('created 4 dataset', w.status.currentMessage())

    def test_sector_create_button_honors_selection_and_does_not_depend_on_plot(self):
        w = self.add_source()
        w.list_freq.clearSelection()
        w.list_freq.item(1).setSelected(True)
        controls = w._plot_contexts['plotting'].analysis_controls
        controls.set_sector_settings('-10:10:20', 'mean', 90, unit='deg')
        dialog = SectorStatisticsDialog(controls, [-10, 0, 10, 20], parent=w)
        self.addCleanup(dialog.deleteLater)
        dialog.btn_create_datasets.click()
        self._wait_for_background()
        self.assertEqual(w.table.rowCount(), 4, w.status.currentMessage())
        outputs = [w.table.item(row, 0).data(Qt.UserRole) for row in range(1, 4)]
        self.assertEqual([out.azimuths.tolist() for out in outputs], [[-10], [0], [10, 20]])
        for out in outputs:
            np.testing.assert_array_equal(out.frequencies, [9])
            self.assertTrue(np.isnan(out.phase).all())

    def test_single_band_action_recipe_replays(self):
        w = self.add_source()
        w.action_recorder.start_recording()
        w._create_banded_statistics_datasets(
            [('Example', w.table.item(0, 0).data(Qt.UserRole))],
            [dict(azimuth_band=[-10, 0])], statistic='percentile', percentile=80,
            axes=['azimuth'], interpolate=False, operation_title='Band percentile')
        self._wait_for_background()
        w.action_recorder.stop_recording()
        self.assertFalse(w.action_recorder.capture.error)
        replay = w.action_recorder.capture.recipe.run(source())
        expected = w.table.item(1, 0).data(Qt.UserRole)
        np.testing.assert_allclose(replay.power, expected.power)

    def test_invalid_bounds_keep_dialog_open(self):
        dialog = PercentileDialog(self.window)
        self.addCleanup(dialog.deleteLater)
        dialog.frequency_bands.setChecked(True)
        dialog.frequency_bands.add_band(10, 8)
        dialog.accept()
        self.assertEqual(dialog.result(), QDialog.Rejected)
        self.assertIn('Stop above Start', dialog.band_error.text())

    def test_sector_datasets_convert_mixed_storage_units(self):
        from PySide6.QtCore import QItemSelectionModel
        w = self.add_source()
        converted = source().convert_axis_units(azimuth='rad', frequency='Hz')
        w._add_dataset_row(converted, 'Radians / Hz', 'Synthetic', '')
        w.table.selectionModel().select(w.table.model().index(1, 0),
            QItemSelectionModel.Select | QItemSelectionModel.Rows)
        controls = w._plot_contexts['plotting'].analysis_controls
        controls.set_sector_settings('-10:10', 'percentile', 75, unit='deg')
        w._create_sector_statistics_datasets()
        self._wait_for_background()
        self.assertEqual(w.table.rowCount(), 4, w.status.currentMessage())
        a, b = [w.table.item(row, 0).data(Qt.UserRole) for row in (2, 3)]
        if a.units['azimuth'] == 'rad':
            a, b = b, a
        np.testing.assert_allclose(a.power, b.power)
        np.testing.assert_allclose(a.azimuths, np.rad2deg(b.azimuths))
        np.testing.assert_allclose(a.frequencies * 1e9, b.frequencies)
