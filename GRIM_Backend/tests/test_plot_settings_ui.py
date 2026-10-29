"""Focused GUI regressions for the independent Plotting/ISAR settings popups."""

from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QScrollArea, QWidget

import GRIM_Backend.ui.app as grim_cut_gui
from GRIM_Backend.plotting.models import PlotContext
from GRIM_Backend.plotting.session import plot_context_facade


@plot_context_facade(PlotContext)
class _SettingsBuilderWindow(QMainWindow):
    """Construct only the QWidget base needed by the settings/context builder."""

    _build_plot_left_context = grim_cut_gui.GrimCutWindow._build_plot_left_context
    _activate_plot_tab = grim_cut_gui.GrimCutWindow._activate_plot_tab
    _clear_zoom_box_drag = grim_cut_gui.GrimCutWindow._clear_zoom_box_drag
    _clear_pan_drag = grim_cut_gui.GrimCutWindow._clear_pan_drag

    def __init__(self) -> None:
        super().__init__()
        self._plot_controls_by_tab: dict[str, dict] = {}
        self._plot_headers = {}
        self._plot_views = {}
        self._plot_control_storage = QWidget(self)
        self._plot_control_storage.hide()

    def _refresh_shared_plot_controls(self):
        pass

    def _schedule_hover(self, *_args) -> None:
        pass

    def _reset_hover_readout(self, *_args) -> None:
        pass

    def _move_shared_right_panel(self, _tab_key: str) -> None:
        pass


class PlotSettingsUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.window = _SettingsBuilderWindow()
        self.plot_panel = QWidget(self.window)
        self.isar_panel = QWidget(self.window)
        self.plot_context = self.window._build_plot_left_context(
            self.plot_panel, "plotting"
        )
        self.isar_context = self.window._build_plot_left_context(
            self.isar_panel, "isar"
        )

    def tearDown(self) -> None:
        self.plot_context.settings_frame.close()
        self.isar_context.settings_frame.close()
        self.window.deleteLater()
        self.app.processEvents()

    @staticmethod
    def _label(popup, text: str) -> QLabel:
        return next(
            label
            for label in popup.content_widget.findChildren(QLabel)
            if label.text() == text
        )

    def show_mode(self, context, mode):
        context.last_plot_mode = mode
        context.plot_ax.clear()
        context.plot_ax.plot([0., 1.], [1., 2.])
        context.settings_frame.plot_controls.refresh_from_canvas()
        context.settings_frame.show()
        self.app.processEvents()
        return context.settings_frame.plot_controls

    def test_unified_name_and_only_current_plot_controls(self):
        for context in (self.plot_context, self.isar_context):
            self.assertEqual(context.settings_frame.windowTitle(), "Plot Settings")
            self.assertEqual(context.btn_settings.text(), "Plot Settings")
            self.assertIn('Create a plot', context.settings_frame.plot_controls.heading.text())
        controls = self.show_mode(self.plot_context, 'frequency')
        controls.tabs.setCurrentIndex(1)
        self.assertTrue(self.plot_context.analysis_controls.combo_sweep_aggregation.isVisible())
        self.assertFalse(self.plot_context.analysis_controls.combo_cdf.isVisible())
        self.assertFalse(self.plot_context.image_analysis_controls.combo_x.isVisible())
        self.assertFalse(self.plot_context.combo_isar_recon.isVisible())
        self.assertFalse(self.plot_context.analysis_controls.spin_sweep_percentile.isVisible())
        combo = self.plot_context.analysis_controls.combo_sweep_aggregation
        combo.setCurrentIndex(combo.findData('percentile'))
        self.assertTrue(self.plot_context.analysis_controls.spin_sweep_percentile.isVisible())
        controls = self.show_mode(self.plot_context, 'waterfall')
        controls.tabs.setCurrentIndex(1)
        self.assertTrue(self.plot_context.image_analysis_controls.combo_x.isVisible())
        self.assertFalse(combo.isVisible())
        controls.tabs.setCurrentIndex(0)
        self.assertTrue(self.plot_context.spin_plot_zmin.isVisible())
        self.show_mode(self.plot_context, 'azimuth_rect')
        self.assertFalse(self.plot_context.spin_plot_zmin.isVisible())
        self.assertFalse(controls.tabs.isTabVisible(1))

    def test_range_image_hides_isar_only_controls_and_reveals_enabled_options(self):
        c = self.isar_context
        controls = self.show_mode(c, 'isar_image')
        controls.tabs.setCurrentIndex(1)
        self.assertTrue(c.combo_isar_recon.isVisible())
        self.assertFalse(c.spin_isar_freq_min.isVisible())
        c.chk_isar_freq_band.setChecked(True)
        self.assertTrue(c.spin_isar_freq_min.isVisible())
        controls.tabs.setCurrentIndex(2)
        self.assertTrue(c.isar_advanced.isVisible())
        self.assertFalse(c.spin_isar_l1_strength.isVisible())
        c.combo_isar_recon.setCurrentIndex(2)
        self.assertTrue(c.spin_isar_l1_strength.isVisible())
        self.show_mode(c, 'az_vs_range')
        controls.tabs.setCurrentIndex(1)
        self.assertTrue(c.combo_isar_window.isVisible())
        self.assertTrue(c.combo_isar_window.isEnabled())
        self.assertTrue(c.chk_isar_flip_y.isVisible())
        self.assertFalse(c.combo_isar_recon.isVisible())
        self.assertFalse(c.chk_isar_flip_x.isVisible())
        self.assertFalse(c.isar_advanced.isVisible())
        self.assertFalse(controls.tabs.isTabVisible(2))
        self.assertEqual(c.btn_isar_apply.text(), 'Apply plot settings')

    def test_failed_or_pending_plot_does_not_replace_current_settings(self):
        c = self.plot_context
        controls = self.show_mode(c, 'waterfall')
        c.last_plot_mode = 'frequency'
        controls.refresh_from_canvas()
        self.assertEqual(controls.mode, 'waterfall')
        c.plot_ax.clear()
        controls.refresh_from_canvas()
        self.assertIsNone(controls.mode)

    def test_wheel_scrolls_without_changing_focused_controls(self):
        from PySide6.QtCore import QPoint, QPointF
        from PySide6.QtGui import QWheelEvent
        c = self.isar_context
        controls = self.show_mode(c, 'isar_image')
        controls.tabs.setCurrentIndex(2)
        popup = c.settings_frame
        popup.resize(480, 300)
        self.app.processEvents()
        for widget in (c.isar_advanced.mode, c.isar_advanced.side, c.spin_isar_az_min):
            widget.setFocus()
            before = widget.currentIndex() if hasattr(widget, 'currentIndex') else widget.value()
            event = QWheelEvent(QPointF(5, 5), QPointF(widget.mapToGlobal(QPoint(5, 5))),
                QPoint(0, 0), QPoint(0, -120), Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
            self.app.sendEvent(widget, event)
            after = widget.currentIndex() if hasattr(widget, 'currentIndex') else widget.value()
            self.assertEqual(before, after)
        self.assertGreater(popup.scroll_area.verticalScrollBar().value(), 0)

    def test_compact_limit_fields_preserve_precision_and_commit_on_enter(self):
        from PySide6.QtTest import QTest, QSignalSpy
        c = self.plot_context
        self.show_mode(c, 'waterfall')
        spin = c.spin_plot_xmin
        exact = -123.123456789012
        spin.setValue(exact)
        self.assertEqual(spin.text(), '-123.123')
        self.assertAlmostEqual(spin.value(), exact, places=12)
        spy = QSignalSpy(spin.valueChanged)
        c.spin_plot_xmax.setFocus()
        self.app.processEvents()
        QTest.mouseClick(spin.lineEdit(), Qt.LeftButton)
        self.app.processEvents()
        self.assertEqual(spin.lineEdit().selectedText(), spin.text())
        spin.interpretText()
        self.assertAlmostEqual(spin.value(), exact, places=12)
        spin.selectAll()
        QTest.keyClicks(spin, '-25.5')
        self.assertEqual(spy.count(), 0)
        QTest.keyClick(spin, Qt.Key_Return)
        self.assertEqual(spin.value(), -25.5)
        self.assertEqual(spy.count(), 1)
        spin.selectAll()
        QTest.keyClicks(spin, '1e-8')
        QTest.keyClick(spin, Qt.Key_Return)
        self.assertEqual(spin.value(), 1e-8)
        self.assertEqual(spin.text(), '1e-08')
        spin.setValue(exact)
        spin.selectAll()
        QTest.keyClicks(spin, '-123.123')
        QTest.keyClick(spin, Qt.Key_Return)
        self.assertEqual(spin.value(), -123.123)
        spin.selectAll()
        QTest.keyClicks(spin, '5')
        QTest.keyClick(spin, Qt.Key_Up)
        QTest.keyClick(spin, Qt.Key_Return)
        self.assertEqual(spin.value(), 6.)

    def test_tab_switch_preserves_independent_settings_and_closes_previous_popup(self) -> None:
        plot_popup = self.plot_context.settings_frame
        isar_popup = self.isar_context.settings_frame
        self.show_mode(self.plot_context, 'frequency')

        self.plot_context.spin_plot_xmin.setValue(-12.0)
        self.isar_context.spin_plot_xmin.setValue(-34.0)
        self.plot_context.btn_settings.setChecked(True)

        self.window._plot_contexts = {
            "plotting": self.plot_context,
            "isar": self.isar_context,
        }
        self.window._active_plot_tab = "plotting"
        self.window._dataset_ops_panel = QWidget(self.window)
        self.window._dataset_ops_visible = False
        with mock.patch.object(self.window, "_move_shared_right_panel"):
            self.window._activate_plot_tab("isar")

        self.app.processEvents()
        self.assertFalse(plot_popup.isVisible())
        self.assertFalse(self.plot_context.btn_settings.isChecked())
        self.assertIs(self.window.combo_isar_recon, self.isar_context.combo_isar_recon)
        self.assertEqual(self.plot_context.spin_plot_xmin.value(), -12.0)
        self.assertEqual(self.window.spin_plot_xmin.value(), -34.0)


from test_plot_analysis_features import _WindowCase


class PlotSettingsIntegrationTests(_WindowCase):
    def test_isar_canvas_limits_edit_without_recomputing_and_apply_stays_available(self):
        from PySide6.QtTest import QTest
        w = self.window
        w._show_isar_workspace()
        self.select_rows(0, freqs=tuple(range(len(self.datasets[0].frequencies))))
        self.plot('_plot_az_vs_range')
        self.assertIn('updated', w.status.currentMessage())
        w.btn_settings.setChecked(True)
        self.app.processEvents()
        controls = w.settings_frame.plot_controls
        self.assertEqual(controls.mode, 'az_vs_range')
        controls.tabs.setCurrentIndex(0)
        self.assertTrue(w.btn_isar_apply.isVisible())
        with mock.patch.object(w, '_plot_az_vs_range', side_effect=AssertionError('recomputed image')):
            spin = w.spin_plot_xmin
            spin.setFocus()
            spin.selectAll()
            QTest.keyClicks(spin, '-0.5')
            QTest.keyClick(spin, Qt.Key_Return)
            self.assertEqual(w.plot_ax.get_xlim()[0], -.5)
            w.spin_plot_zmin.setValue(-35.)
            w.spin_plot_zmax.setValue(5.)
            self.assertEqual(w._az_vs_range_mesh.get_clim(), (-35., 5.))
        w.settings_frame.close()
        w._show_plot_workspace()


if __name__ == "__main__":
    unittest.main()
