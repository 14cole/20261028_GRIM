"""Population, unit, presentation, and recipe checks for statistical reports."""
import math
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

from test_ppt_plot_data import _grid
from GRIM_Backend.reports.statistics import build_statistical_specs
from GRIM_Backend.reports.report import plan_azimuth_slides, export_report_images


class StatisticalDataTests(unittest.TestCase):
    def build(self, grid, **kwargs):
        return build_statistical_specs([("Example", grid)], frequencies=grid.frequencies,
                                       elevation=0., polarization="VV", **kwargs)

    def test_cdf_and_inclusive_exceedance_keep_zeros_ties_and_invalid_counts(self):
        grid = _grid(azimuths=(0, 10, 20, 30, 40, 50), frequencies=(1.,),
                     power=np.array([0., 1., 1., 100., np.nan, np.nan]).reshape(-1, 1, 1, 1))
        cdf, = self.build(grid, kind="cdf")
        exceed, = self.build(grid, kind="exceedance")
        np.testing.assert_allclose(cdf.series[0].x[1:-1], [0., 20.])
        np.testing.assert_allclose(cdf.series[0].y, [25., 75., 100., 100.])
        np.testing.assert_allclose(exceed.series[0].y, [75., 75., 25., 0.])
        self.assertEqual(cdf.series[0].draw_style, "steps-post")
        self.assertEqual(exceed.series[0].draw_style, "steps-pre")
        self.assertEqual(cdf.y_limits, (0., 100.))
        self.assertIn("Zero power retained", cdf.note)
        self.assertIn("Invalid samples excluded", cdf.note)

    def test_periodic_seam_is_counted_once_and_overlay_populations_use_common_directions(self):
        grid = _grid(azimuths=(0, 90, 180, 270, 360), frequencies=(1.,),
                     power=np.array([999., 1., 2., 3., 4.]).reshape(-1, 1, 1, 1))
        plot, = self.build(grid)
        np.testing.assert_allclose(plot.series[0].y, [0., 25., 50., 75., 100., 100.])
        self.assertAlmostEqual(plot.series[0].x[-2], 10*np.log10(4.))
        other = _grid(azimuths=(90, 270), frequencies=(1.,), power=2.)
        plot, = build_statistical_specs([("A", grid), ("B", other)], frequencies=(1.,),
                                        elevation=0., polarization="VV")
        np.testing.assert_allclose(plot.series[0].x[1:-1], [0., 10*np.log10(3.)])

    def test_sector_mean_reduces_linear_power_and_assigns_boundaries_once(self):
        grid = _grid(azimuths=(0, 10, 20, 30), frequencies=(1.,),
                     power=np.array([1., 9., 0., 100.]).reshape(-1, 1, 1, 1))
        plot, = self.build(grid, kind="sector_stats", sector_width_deg=20.)
        np.testing.assert_allclose(plot.series[0].x, [0, 20, 20, 20, 30, 30])
        np.testing.assert_allclose(plot.series[0].y, [10*np.log10(5), 10*np.log10(5), np.nan,
                                                   10*np.log10(50), 10*np.log10(50), np.nan], equal_nan=True)
        percentile, = self.build(grid, kind="sector_stats", sector_width_deg=360.,
                                  statistic="percentile", percentile=50.)
        self.assertEqual(percentile.series[0].y[0], 0.)  # nearest rank is power 1

    def test_sector_empty_bins_and_zero_scores_remain_distinct(self):
        grid = _grid(azimuths=(0, 10, 90), frequencies=(1.,),
                     power=np.array([0., 0., 2.]).reshape(-1, 1, 1, 1))
        plot, = self.build(grid, kind="sector_stats", sector_width_deg=30.)
        self.assertEqual(plot.series[0].y[0], -math.inf)
        self.assertTrue(math.isnan(plot.series[0].y[3]))
        self.assertAlmostEqual(plot.series[0].y[6], 10*np.log10(2.))
        self.assertIn("not drawn", plot.note)

    def test_native_radians_and_hz_and_dbke_use_each_actual_frequency(self):
        grid = _grid(azimuths=np.deg2rad([0., 10., 20.]), angle_unit="rad",
                     frequencies=(1e9, 2e9), frequency_unit="Hz", power=1.,
                     quantity="sigma_2d", log_unit="dBke")
        plots = self.build(grid, kind="sector_stats", sector_width_deg=30.)
        np.testing.assert_allclose(plots[0].series[0].x[:2], [0., 20.])
        self.assertAlmostEqual(plots[1].series[0].y[0]-plots[0].series[0].y[0], 10*np.log10(2.))
        self.assertIn("2 GHz", plots[1].title)
        self.assertIn("dBke", plots[1].y_label)

    def test_dual_polarization_panels_and_master_legend_stay_separate(self):
        grid = _grid(polarizations=("VV", "HH"))
        plots = build_statistical_specs([("Example", grid)], frequencies=grid.frequencies,
                                        elevation=0., polarization="VV and HH")
        self.assertEqual(len(set(p.plot_id for p in plots)), 4)
        plan = plan_azimuth_slides(plots, master_legend=True,
                                   polarization_labels=("VV", "VV", "HH", "HH"))
        self.assertEqual(len(plan.slides), 2)
        self.assertTrue(all(len(s.master_legend) == 1 for s in plan.slides))

    def test_all_zero_cdf_and_missing_cut_rejection(self):
        plot, = self.build(_grid(frequencies=(1.,), power=0.))
        self.assertEqual(plot.series[0].y, (100., 100.))
        with self.assertRaisesRegex(ValueError, "no valid statistical samples"):
            self.build(_grid(power=np.nan))
        with self.assertRaisesRegex(ValueError, "distinct common"):
            self.build(_grid(azimuths=(0., 360.)))

    def test_each_new_type_exports_png_with_its_caption_and_population_note(self):
        with tempfile.TemporaryDirectory() as temporary:
            for kind in ("cdf", "exceedance", "sector_stats"):
                plots = self.build(_grid(frequencies=(1.,), power=0.), kind=kind)
                plan = plan_azimuth_slides(plots, master_legend=True)
                output = export_report_images(plan, Path(temporary)/kind)
                manifest = json.loads((output/'manifest.json').read_text())
                record = manifest['slides'][0]['plots'][0]
                self.assertEqual(record['type'], kind)
                self.assertIn('Zero', record['note'])
                self.assertGreater((output/record['relative_path']).stat().st_size, 100)


class StatisticalWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from GRIM_Backend.reports.workspace import PptWorkspace
        self.widget = PptWorkspace()
        self.widget.set_dataset_catalog([("a", "Example", _grid())])
        self.widget.select_dataset_ids(["a"])

    def tearDown(self):
        self.widget.dispose()
        self.widget.close()
        self.widget.deleteLater()
        self.app.processEvents()

    def test_new_kinds_preview_and_axis_controls(self):
        w = self.widget
        w.y_min_spin.setValue(-40.)
        w.scale_mode_combo.setCurrentIndex(w.scale_mode_combo.findData("fixed"))
        for kind in ("cdf", "exceedance", "sector_stats"):
            w.set_plot_kind(kind)
            self.assertTrue(w.build_preview(), w.last_error)
            plot = w.preview_plan.slides[0].plots[0].plot
            self.assertEqual(plot.kind, kind)
            self.assertFalse(w.frequency_box.isHidden())
            self.assertTrue(w.azimuth_combo.isHidden())
            if kind != "sector_stats":
                self.assertEqual(plot.y_limits, (0., 100.))
                self.assertFalse(w.scale_mode_combo.isEnabled())
                w._use_data_x_bounds()
                self.assertFalse(w.last_error)
        self.assertEqual(w.y_min_spin.value(), -40.)
        self.assertTrue(w.scale_mode_combo.isEnabled())

    def test_statistical_recipe_round_trip_and_old_recipe_defaults(self):
        w = self.widget
        w.set_plot_kind("sector_stats")
        w.sector_width_spin.setValue(45.)
        w.sector_statistic_combo.setCurrentIndex(w.sector_statistic_combo.findData("percentile"))
        w.sector_percentile_spin.setValue(75.)
        state = w.capture_report_setup()
        w.set_plot_kind("frequency")
        w.apply_report_setup(state)
        self.assertEqual(w.plot_type_combo.currentData(), "sector_stats")
        self.assertEqual(w.sector_percentile_spin.value(), 75.)
        self.assertEqual(w.sector_width_spin.value(), 45.)
        del state['combos']['sector_statistic_combo']
        del state['spins']['sector_width_spin']
        del state['spins']['sector_percentile_spin']
        state['combos']['plot_type_combo'] = 'azimuth_rect'
        w.apply_report_setup(state)
        self.assertEqual(w.sector_width_spin.value(), 30.)
        self.assertEqual(w.sector_statistic_combo.currentData(), "mean")

    def test_cdf_custom_axis_extends_tails_and_preserves_steps(self):
        w = self.widget
        w.set_plot_kind("cdf")
        w.x_scale_mode_combo.setCurrentIndex(w.x_scale_mode_combo.findData("fixed"))
        w.x_min_spin.setValue(-100.)
        w.x_max_spin.setValue(100.)
        plot = w._build_plan().slides[0].plots[0].plot
        self.assertEqual(plot.series[0].x[0], -100.)
        self.assertEqual(plot.series[0].x[-1], 100.)
        self.assertEqual(plot.series[0].x[1:-1], (0.,))
        self.assertEqual(plot.series[0].draw_style, "steps-post")
        w._use_data_x_bounds()
        self.assertGreater(w.x_min_spin.value(), -100.)
        self.assertLess(w.x_max_spin.value(), 100.)

    def test_all_zero_sectors_are_reported_without_inventing_a_finite_level(self):
        w = self.widget
        w.set_dataset_catalog([("a", "Zero", _grid(power=0.))])
        w.set_plot_kind("sector_stats")
        plot = w._build_plan().slides[0].plots[0].plot
        self.assertTrue(all(math.isnan(y) or y == -math.inf for y in plot.series[0].y))
        self.assertIn("not drawn", plot.note)
