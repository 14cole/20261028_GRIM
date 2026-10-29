"""Real button routing and retained state in the consolidated plot workspace."""
import time
from unittest import mock
import unittest

import numpy as np
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import test_gui_shell as shell
from test_isar_improvements import grid


class SharedPlotWorkspaceTests(unittest.TestCase):
    setUp = shell.UnifiedGuiShellTest.setUp
    tearDown = shell.UnifiedGuiShellTest.tearDown

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def settle(self):
        for _ in range(3):
            self.app.processEvents()

    def test_display_toggles_stay_visible_and_follow_plot_support(self):
        w = self.window
        w.show()
        w.analysis_controls.set_sector_settings(boxes=[dict(
            name='All', azimuth_band=[0., 360.], frequency_band=[9e9, 10e9],
        )])
        controls = w._plot_controls_by_tab['plotting']
        pbp, phase = controls['pbp'], controls['phase']
        self.assertFalse(pbp.isEnabled())
        self.assertFalse(phase.isEnabled())
        for role, supports_pbp, supports_phase in (
            ('azimuth_rect', True, True), ('azimuth_polar', True, True),
            ('frequency', True, True), ('elevation_sweep', False, True),
            ('waterfall', False, True), ('compare', False, True),
            ('delta_map', False, False), ('sector_stats', False, False),
        ):
            with self.subTest(plot=role):
                controls[role].click()
                self.assertEqual(pbp.isEnabled(), supports_pbp)
                self.assertEqual(phase.isEnabled(), supports_phase)
                for button in (pbp, phase):
                    self.assertTrue(w.plot_control_tabs.header.isAncestorOf(button))
                    self.assertTrue(button.isVisible())

        controls['azimuth_rect'].click()
        pbp.click()
        phase.click()
        w.plot_control_tabs.setCurrentIndex(2)
        self.assertTrue(pbp.isVisible())
        self.assertTrue(phase.isVisible())
        w.plot_control_tabs.setCurrentIndex(1)
        for role in ('pbp', 'phase'):
            placeholder = w._unavailable_plot_controls[role]
            self.assertTrue(placeholder.isVisible())
            self.assertFalse(placeholder.isEnabled())
        w.plot_control_tabs.setCurrentIndex(0)
        self.assertTrue(pbp.isChecked())
        self.assertTrue(phase.isChecked())
        # Switching to magnitude statistics clears incompatible settings
        # without emitting toggles that would launch a second plot.
        with mock.patch.object(w, '_on_polarization_selection_changed') as changed:
            controls['sector_stats'].click()
            changed.assert_not_called()
        self.assertFalse(pbp.isChecked())
        self.assertFalse(phase.isChecked())
        self.assertFalse(pbp.isEnabled())
        self.assertFalse(phase.isEnabled())

    def test_settings_and_shared_controls_follow_last_view_without_losing_state(self):
        w = self.window
        w.show()
        w.btn_hold.setChecked(True)
        plot_canvas = w.plot_canvas
        w.spin_plot_xmin.setValue(-23.)
        w.btn_settings.click()
        self.settle()
        plot_popup = w.settings_frame
        self.assertTrue(plot_popup.isVisible())
        w.plot_control_tabs.setCurrentIndex(1)
        self.settle()
        self.assertFalse(plot_popup.isVisible())
        self.assertEqual(w.btn_settings.text(), 'Plot Settings')
        isar_canvas = w.plot_canvas
        self.assertIsNot(isar_canvas, plot_canvas)
        w.spin_plot_zmin.setValue(-42.)
        w.plot_control_tabs.setCurrentIndex(2)
        self.settle()
        self.assertIs(w.plot_canvas, isar_canvas)
        self.assertEqual(w.btn_settings.text(), 'Plot Settings')
        controls = w._plot_controls_by_tab['isar']
        controls['overlays'].click()
        self.assertTrue(w.spatial_overlays.isVisible())
        controls['overlays'].click()
        w.chk_plot_legend.click()
        self.assertFalse(w.chk_plot_legend.isChecked())
        w.plot_control_tabs.setCurrentIndex(0)
        self.settle()
        self.assertEqual(w.btn_settings.text(), 'Plot Settings')
        self.assertIs(w.plot_canvas, plot_canvas)
        self.assertTrue(w.btn_hold.isChecked())
        self.assertTrue(w.chk_plot_legend.isChecked())
        self.assertEqual(w.spin_plot_xmin.value(), -23.)
        w.plot_control_tabs.setCurrentIndex(2)
        self.assertEqual(w._active_plot_tab, 'plotting')
        w.main_tabs.setCurrentWidget(w.tab_python)
        w.main_tabs.setCurrentWidget(w.tab_simple_plots)
        self.assertEqual(w.plot_control_tabs.currentIndex(), 2)
        self.assertIs(w.plot_canvas, plot_canvas)
        w.plot_control_tabs.setCurrentIndex(1)
        self.assertEqual(w.spin_plot_zmin.value(), -42.)
        self.assertFalse(w.chk_plot_legend.isChecked())

    def test_real_isar_and_downrange_buttons_then_shared_measure_and_clear(self):
        w = self.window
        w.show()
        source = grid(az=np.linspace(-5., 5., 17), freq=np.linspace(9e9, 11e9, 17))
        w._add_dataset_row(source, 'Origin point', 'Synthetic', 'point.grim')
        w.table.selectRow(0)
        for listing in (w.list_pol, w.list_az, w.list_elev, w.list_freq):
            listing.selectAll()
        w.plot_control_tabs.setCurrentIndex(1)
        controls = w._plot_controls_by_tab['isar']
        with mock.patch('GRIM_Backend.ui.app.QMessageBox.warning') as warnings:
            controls['isar_image'].click()
            deadline = time.monotonic() + 15
            while getattr(w, '_isar_busy', False) and time.monotonic() < deadline:
                QTest.qWait(10)
            self.assertFalse(getattr(w, '_isar_busy', False))
            self.settle()
            self.assertEqual(w.last_plot_mode, 'isar_image', w.status.currentMessage())
            self.assertTrue(w._isar_figure_is_current())
            self.assertTrue(w.plot_ax.collections or w.plot_ax.images)
            controls['az_vs_range'].click()
            deadline = time.monotonic() + 15
            while getattr(w, '_ordinary_plot_pending', False) and time.monotonic() < deadline:
                QTest.qWait(10)
            self.assertEqual(w.last_plot_mode, 'az_vs_range', w.status.currentMessage())
            self.assertTrue(w.plot_ax.collections or w.plot_ax.images)
            w.plot_control_tabs.setCurrentIndex(2)
            self.settle()
            controls['measure'].click()
            self.assertTrue(w.inline_analysis._image_measurement_active)
            controls['clear'].click()
            self.assertFalse(w.plot_ax.collections)
            self.assertFalse(w.plot_ax.images)
            self.assertFalse(w._isar_figure_is_current())
            warnings.assert_not_called()

    def test_range_convention_correction_through_real_settings(self):
        from test_isar_accuracy_2026_10_17 import grid as point_grid, AZ, F
        w = self.window
        w.show()
        source = point_grid(AZ, F, [(.3,.6,1.)], negative_time=True)
        source.units['time_convention'] = 'exp(+jwt)'
        source.extra['range_phase_convention'] = 'S~exp(+j*2*k*R)'
        w._add_dataset_row(source, 'Signed target', 'Synthetic', 'signed.grim')
        w.table.selectRow(0)
        for listing in (w.list_pol, w.list_az, w.list_elev, w.list_freq):
            listing.selectAll()
        w.plot_control_tabs.setCurrentIndex(1)
        controls = w._plot_controls_by_tab['isar']
        w.combo_isar_units.setCurrentText('m')
        controls['az_vs_range'].click()
        self.assertIn('Flip Y setting is preserved', w.status.currentMessage())
        self.assertFalse(w.chk_isar_flip_x.isEnabled())
        w.chk_isar_flip_y.setChecked(True)
        w.btn_isar_apply.click()
        deadline = time.monotonic()+15
        while getattr(w,'_ordinary_plot_pending',False) and time.monotonic()<deadline:
            QTest.qWait(10)
        self.settle()
        mesh = w._az_vs_range_mesh
        iy, _ = np.unravel_index(np.argmax(mesh.get_array()),mesh.get_array().shape)
        edges = mesh._grim_rectilinear_data[1]
        self.assertAlmostEqual((edges[iy]+edges[iy+1])/2,.6,delta=.025)
        self.assertTrue(mesh._grim_image_record.metadata['range_mirrored'])
        controls['isar_image'].click()
        self.assertTrue(w.chk_isar_flip_x.isEnabled())
        deadline = time.monotonic()+15
        while getattr(w, '_isar_busy', False) and time.monotonic()<deadline:
            QTest.qWait(10)
        self.assertIn('updated', w.status.currentMessage())

    def test_negative_time_plots_automatically_without_flips(self):
        from test_isar_accuracy_2026_10_17 import grid as point_grid, AZ, F
        w=self.window
        w.show()
        source=point_grid(AZ,F,[(.3,.6,1.)],negative_time=True)
        source.extra['range_phase_convention']='S~exp(+j*2*k*R)'
        source.extra['phase_reference']='none'
        source.extra['measurement_geometry']='unknown'
        source.extra['motion_compensation']='unspecified'
        before=source.rcs_slice((slice(None),0,slice(None),0)).copy()
        w._add_dataset_row(source,'Negative-time target','Synthetic','negative.grim')
        w.table.selectRow(0)
        for listing in (w.list_pol,w.list_az,w.list_elev,w.list_freq):
            listing.selectAll()
        w.plot_control_tabs.setCurrentIndex(1)
        w.combo_isar_units.setCurrentText('m')
        controls=w._plot_controls_by_tab['isar']
        controls['isar_image'].click()
        deadline=time.monotonic()+15
        while getattr(w,'_isar_busy',False) and time.monotonic()<deadline:
            QTest.qWait(10)
        self.settle()
        self.assertTrue(w._isar_figure_is_current(),w.status.currentMessage())
        self.assertIn('negative-time samples normalized automatically',w.status.currentMessage())
        self.assertIn('missing or ambiguous',w.status.currentMessage())
        image=w.plot_ax.images[0]
        iy,ix=np.unravel_index(np.argmax(image.get_array()),image.get_array().shape)
        ny,nx=image.get_array().shape
        x0,x1,y0,y1=image.get_extent()
        self.assertAlmostEqual(x0+(ix+.5)*(x1-x0)/nx,.3,delta=.035)
        self.assertAlmostEqual(y0+(iy+.5)*(y1-y0)/ny,.6,delta=.035)
        controls['az_vs_range'].click()
        deadline=time.monotonic()+15
        while getattr(w,'_ordinary_plot_pending',False) and time.monotonic()<deadline:
            QTest.qWait(10)
        mesh=w._az_vs_range_mesh
        iy,_=np.unravel_index(np.argmax(mesh.get_array()),mesh.get_array().shape)
        edges=mesh._grim_rectilinear_data[1]
        self.assertAlmostEqual((edges[iy]+edges[iy+1])/2,.6,delta=.025)
        np.testing.assert_array_equal(before,source.rcs_slice((slice(None),0,slice(None),0)))
