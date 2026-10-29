"""Sector populations must retain physical zero and distinguish missing power."""

from __future__ import annotations

from io import BytesIO
from unittest import mock

import numpy as np
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QMenu

from GRIM_Backend.plotting.modes import sector_stats_mode
from test_plot_analysis_features import _WindowCase


class SectorZeroPowerTests(_WindowCase):
    def sector(self, powers, *, linear=False, statistic="mean", percentile=25.0,
               text="-2:2", interpolate=False):
        self.datasets[0].rcs_power[:] = np.asarray(powers)[:, None, None, None]
        self.select_rows(0)
        self.window.combo_plot_scale.setCurrentIndex(
            self.window.combo_plot_scale.findData("linear" if linear else "dbsm")
        )
        self.window.analysis_controls.set_sector_settings(
            text, statistic, percentile, interpolate=interpolate
        )
        self.plot("_plot_sector_stats")
        return self.window.plot_figure._grim_sector_table

    def assert_line_level(self, expected):
        (line,) = self.lines(self.keys[0])
        np.testing.assert_allclose(line.get_ydata(), [expected, expected, np.nan])

    def copy_sector_table(self):
        class CopySectorMenu(QMenu):
            def exec(self, _position):
                return next(action for action in self.actions()
                            if action.text() == "Copy sector table")

        with mock.patch("GRIM_Backend.ui.dataset_actions.QMenu", CopySectorMenu), \
                mock.patch.object(self.window.spatial_overlays, "context_menu", return_value=False), \
                mock.patch.object(self.window, "_marker_context_menu", return_value=False), \
                mock.patch.object(self.window, "_dataset_line_at_canvas_position", return_value=None):
            self.window._on_plot_context_menu(QPoint(1, 1))
        return self.app.clipboard().text().splitlines()

    def test_percentile_option_matches_plot_and_copied_table_in_both_scales(self):
        for linear in (True, False):
            for interpolate, expected_power in ((True, 61.2), (False, 100.0)):
                with self.subTest(linear=linear, interpolate=interpolate):
                    table = self.sector(
                        [0, 1, 2, 3, 100], linear=linear, statistic="percentile",
                        percentile=90.0, interpolate=interpolate,
                    )
                    expected = expected_power if linear else 10.0 * np.log10(expected_power)
                    self.assertEqual(table["interpolate"], interpolate)
                    self.assertEqual(
                        table["percentile_method"], "linear" if interpolate else "inverted_cdf"
                    )
                    self.assertEqual(table["rows"][0][5], 5)
                    self.assertAlmostEqual(table["rows"][0][-1], expected)
                    self.assert_line_level(expected)
                    header, row = self.copy_sector_table()
                    self.assertEqual("nearest rank" in header, not interpolate)
                    np.testing.assert_allclose(float(row.split("\t")[-1]), expected, rtol=1e-5)

    def test_held_percentiles_keep_distinct_interpolation_methods(self):
        self.sector(
            [0, 1, 2, 3, 100], linear=True, statistic="percentile", percentile=90.0,
            interpolate=True
        )
        self.window.btn_hold.setChecked(True)
        self.window.analysis_controls.set_sector_settings(
            "-2:2", "percentile", 90.0, interpolate=False
        )
        self.plot("_plot_sector_stats")
        lines = self.lines(self.keys[0])
        self.assertEqual(len(lines), 2)
        np.testing.assert_allclose(sorted(line.get_ydata()[0] for line in lines), [61.2, 100])
        self.assertEqual(sum("nearest rank" in line.get_label() for line in lines), 1)
        self.plot("_plot_sector_stats")
        self.assertEqual(len(self.lines(self.keys[0])), 2)

    def test_method_change_updates_percentile_table_without_duplicating_held_mean(self):
        self.sector([0, 1, 2, 3, 100], linear=True, percentile=90.0, interpolate=True)
        self.window.btn_hold.setChecked(True)
        self.window.analysis_controls.set_sector_settings(
            "-2:2", "mean", 90.0, interpolate=False
        )
        self.plot("_plot_sector_stats")
        self.assert_line_level(21.2)
        self.assertEqual(self.window.plot_figure._grim_sector_table["rows"][0][-1], 100.0)

    def test_nearest_rank_filters_invalid_values_and_preserves_other_statistics(self):
        powers = np.asarray([-1.0, np.nan, np.inf, -np.inf, 0.0, 4.0])
        members = np.ones(powers.size, dtype=bool)
        for percentile, expected in ((0, 0), (25, 0), (50, 0), (75, 4), (100, 4)):
            with self.subTest(percentile=percentile):
                stats = sector_stats_mode._sector_linear_statistics(
                    powers, members, percentile
                )
                self.assertEqual(stats, {
                    "count": 2, "mean": 2.0, "median": 2.0, "min": 0.0,
                    "max": 4.0, "percentile": expected,
                })
        empty = sector_stats_mode._sector_linear_statistics(
            powers, ~members, 90, interpolate=False
        )
        self.assertEqual(empty.pop("count"), 0)
        self.assertTrue(np.isnan(list(empty.values())).all())

    def test_audit_mixed_zero_case_has_five_samples_and_unbiased_log_mean(self):
        table = self.sector([0, 1, 1, 1, 1])
        row, = table["rows"]
        self.assertEqual(row[5], 5)
        expected_mean = -0.969100130080564  # 10*log10(4/5), not mean(dB)
        np.testing.assert_allclose(row[6:], [expected_mean, 0, -np.inf, 0, 0])
        self.assert_line_level(expected_mean)
        cells = sector_stats_mode.table_text(table).splitlines()[1].split("\t")
        self.assertEqual(cells[5], "5")
        self.assertAlmostEqual(float(cells[6]), expected_mean, places=6)
        self.assertEqual(cells[8], "-inf")

    def test_zero_majority_counts_in_mean_median_and_interpolated_percentile(self):
        for linear in (True, False):
            with self.subTest(linear=linear):
                table = self.sector([0, 0, 0, 1, 4], linear=linear, percentile=62.5, interpolate=True)
                row, = table["rows"]
                # Rank 2.5 in the sorted sample interpolates halfway from 0 to 1.
                expected = [1.0, 0.0, 0.0, 4.0, 0.5]
                if not linear:
                    expected = [0.0, -np.inf, -np.inf, 6.020599913279624, -3.010299956639812]
                self.assertEqual(row[5], 5)
                np.testing.assert_allclose(row[6:], expected)
                self.assert_line_level(expected[0])

    def test_all_zero_linear_draws_zero_and_copies_zero_statistics(self):
        table = self.sector([0, 0, 0, 0, 0], linear=True)
        row, = table["rows"]
        self.assertEqual(row[5], 5)
        np.testing.assert_array_equal(row[6:], np.zeros(5))
        self.assert_line_level(0.0)
        self.assertFalse(self.window.plot_ax.texts)
        self.assertNotIn("No finite levels", self.window.status.currentMessage())

        # Exercise the actual Copy sector table menu path, not only formatting.
        copied = self.copy_sector_table()[1].split("\t")
        self.assertEqual(copied[5:], ["5", "0", "0", "0", "0", "0"])

    def test_all_zero_log_reports_negative_infinity_in_table_plot_and_export(self):
        table = self.sector([0, 0, 0, 0, 0])
        row, = table["rows"]
        self.assertEqual(row[5], 5)
        self.assertTrue(np.isneginf(row[6:]).all())
        self.assertEqual(self.lines(self.keys[0]), [])
        self.assertIn("zero-power sector level", self.window.status.currentMessage())
        self.assertNotIn("No finite levels", self.window.status.currentMessage())
        self.assertEqual(self.window.plot_ax.get_ylabel(), "RCS mean (dBsm)")
        text, = self.window.plot_ax.texts
        self.assertIn("zero-power", text.get_text())
        self.assertIn("-inf", text.get_text())
        self.assertNotIn("nan", sector_stats_mode.table_text(table))
        exported = BytesIO()
        self.window.plot_figure.savefig(exported, format="svg")
        self.assertIn(b"zero-power sector level", exported.getvalue())

    def test_zero_selected_quantile_is_disclosed_and_note_does_not_accumulate(self):
        self.sector([0, 0, 0, 1, 4], statistic="median")
        self.assertEqual(self.lines(self.keys[0]), [])
        self.assertIn("zero-power sector level", self.window.status.currentMessage())
        self.plot("_plot_sector_stats")
        self.assertEqual(len(self.window.plot_ax.texts), 1)
        self.window.btn_hold.setChecked(True)
        self.plot("_plot_sector_stats")
        self.assertEqual(len(self.window.plot_ax.texts), 1)
        self.window.btn_hold.setChecked(False)
        self.sector([1, 1, 1, 1, 1])
        self.assertFalse(self.window.plot_ax.texts)

    def test_negative_and_missing_samples_are_excluded_without_losing_zero(self):
        for invalid in (-1.0, np.nan, np.inf, -np.inf):
            with self.subTest(invalid=invalid):
                table = self.sector([invalid, np.nan, np.inf, 0, 4], linear=True)
                row, = table["rows"]
                self.assertEqual(row[5], 2)
                np.testing.assert_allclose(row[6:], [2, 2, 0, 4, 1])
                self.assert_line_level(2.0)

    def test_empty_sector_is_missing_instead_of_physical_zero(self):
        table = self.sector([0, 0, 0, 0, 0], text="90:100")
        row, = table["rows"]
        self.assertEqual(row[5], 0)
        self.assertTrue(np.isnan(row[6:]).all())
        self.assertIn("No finite levels", self.window.status.currentMessage())
        self.assertFalse(self.window.plot_ax.texts)

    def test_zero_and_positive_statistics_preserve_frequency_dependent_dbke(self):
        self.datasets[0].units.update(rcs_linear_quantity="width_2d", rcs_log_unit="dBke")
        table = self.sector([0, 1, 1, 1, 1])
        row, = table["rows"]
        offset = 10.0 * np.log10(2.0 * np.pi * 9.0e9 / 299_792_458.0)
        np.testing.assert_allclose(
            row[6:], [-0.969100130080564 + offset, offset, -np.inf, offset, offset]
        )
        self.assertEqual(table["unit"], "dBke")
        self.assert_line_level(-0.969100130080564 + offset)
