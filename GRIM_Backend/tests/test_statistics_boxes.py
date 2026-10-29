"""Box populations respect explicit endpoints without circular aliases."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.statistics_bands import band_statistics_dataset
from GRIM_Backend.datasets.statistics_boxes import box_specs
from GRIM_Backend.plotting.modes import sector_stats_mode
import test_gui_shell as shell


def source(unit='deg'):
    angles = np.arange(0., 361., 10.)
    return RcsGrid(np.deg2rad(angles) if unit == 'rad' else angles,
                   [0.], [9.], ['VV'], rcs_power=(angles + 1).reshape(-1, 1, 1, 1),
                   units={'azimuth': unit, 'elevation': 'deg', 'frequency': 'GHz'})


def box(start, stop):
    return dict(name=f'{start} to {stop}', azimuth_band=[start, stop],
                frequency_band=[9e9, 9e9])


@pytest.mark.parametrize('unit', ['deg', 'rad'])
@pytest.mark.parametrize('bounds, expected', [
    ((90, 360), np.arange(90., 361., 10.)),
    ((0, 30), np.arange(0., 31., 10.)),
    ((0, 360), np.arange(0., 361., 10.)),
    ((350, 10), np.array([0., 10., 350., 360.])),
])
def test_box_dataset_coordinates_and_population(unit, bounds, expected):
    original = source(unit)
    spec = box_specs([box(*bounds)])[0]
    result = band_statistics_dataset(original, statistic='mean',
                                     axes=['azimuth', 'frequency'], **spec)
    actual = np.rad2deg(result.azimuths) if unit == 'rad' else result.azimuths
    np.testing.assert_allclose(actual, expected, atol=1e-12)
    np.testing.assert_allclose(result.power, np.mean(expected + 1))
    assert len(original.azimuths) == 37


class BoxStatisticsGuiTests(unittest.TestCase):
    setUp = shell.UnifiedGuiShellTest.setUp
    tearDown = shell.UnifiedGuiShellTest.tearDown
    _wait_for_background = shell.UnifiedGuiShellTest._wait_for_background

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_box_plot_and_created_datasets_use_the_same_population(self):
        w = self.window
        w._add_dataset_row(source(), 'Seam samples', 'Synthetic', '')
        w.table.selectRow(0)
        for listing in (w.list_az, w.list_elev, w.list_freq, w.list_pol):
            listing.selectAll()
        controls = w._plot_contexts['plotting'].analysis_controls
        controls.set_sector_settings(
            boxes=[box(90, 360), box(0, 30), box(0, 360), box(350, 10)], statistic='mean')
        sector_stats_mode.render(w)
        table = w.plot_figure._grim_sector_table
        self.assertEqual([row[5] for row in table['rows']], [28, 4, 37, 4])
        w._create_sector_statistics_datasets()
        self._wait_for_background()
        self.assertEqual(w.table.rowCount(), 5, w.status.currentMessage())
        for row, expected in ((1, np.arange(90., 361., 10.)), (2, np.arange(0., 31., 10.)),
                              (3, np.arange(0., 361., 10.)), (4, [0., 10., 350., 360.])):
            result = w.table.item(row, 0).data(Qt.UserRole)
            np.testing.assert_array_equal(result.azimuths, expected)
            np.testing.assert_allclose(result.power, np.mean(np.asarray(expected) + 1))
