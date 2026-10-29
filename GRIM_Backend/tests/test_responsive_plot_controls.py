"""Real Qt geometry checks for the width-aware plot toolbars."""

import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, QSettings, QSize
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QToolButton, QVBoxLayout, QWidget

from GRIM_Backend.ui.app import GrimCutWindow, PLOTTING_CONTROL_GROUPS
from GRIM_Backend.ui.responsive_controls import ResponsiveButtonPanel, ResponsiveControlTabs


class ResponsivePlotControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.original_font = cls.app.font()
        # The offscreen Windows font fallback has unusually wide metrics.
        # Exercise the same desktop font as the existing compact-window suite.
        font_path = Path("C:/Windows/Fonts/segoeui.ttf")
        if font_path.exists():
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                cls.app.setFont(QFont(families[0], 9))

    @classmethod
    def tearDownClass(cls):
        cls.app.setFont(cls.original_font)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.window = GrimCutWindow(settings=QSettings(
            str(Path(self.temp.name) / "window.ini"), QSettings.IniFormat,
        ))
        self.window.show()
        self.groups = self.window.findChild(ResponsiveControlTabs, "plottingControlTabs")

    def tearDown(self):
        self.window.hide()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.temp.cleanup()

    def settle(self):
        # Parent height-for-width negotiation can need a second layout pass.
        for _ in range(5):
            self.app.processEvents()

    def assert_panel_fits(self, panel):
        widgets = [panel.flow.itemAt(index).widget() for index in range(panel.flow.count())]
        rects = [QRect(widget.mapTo(panel, QPoint()), widget.size()) for widget in widgets]
        for index, (widget, rect) in enumerate(zip(widgets, rects)):
            self.assertTrue(widget.isVisible(), widget.objectName())
            self.assertTrue(panel.rect().contains(rect), (rect, panel.rect()))
            for prior in rects[:index]:
                self.assertFalse(prior.intersects(rect), (prior, rect))
        return len({rect.y() for rect in rects})

    def test_all_three_button_groups_reflow_without_clipping(self):
        rows = {}
        for width in (1200, 1366, 1920, 2400, 1200):
            self.window.resize(width, 800)
            for page_index in range(3):
                self.groups.setCurrentIndex(page_index)
                self.settle()
                self.assertEqual(self.window.size(), QSize(width, 800))
                rows[page_index, width] = self.assert_panel_fits(self.groups.currentWidget())
                self.assert_panel_fits(self.groups.header)
        for page in range(3):
            self.assertGreaterEqual(rows[page, 1200], rows[page, 2400])
        self.assertGreater(rows[0, 1200], rows[0, 2400])

    def test_sidebar_splitter_also_reflows_buttons(self):
        self.window.resize(1366, 800)
        splitter = self.window._plot_splitters['plotting']
        for page_index in (0, 2):
            self.groups.setCurrentIndex(page_index)
            splitter.setSizes([760, 0, 400])
            self.settle()
            narrow_rows = self.assert_panel_fits(self.groups.currentWidget())
            splitter.setSizes([220, 0, 1100])
            self.settle()
            wide_rows = self.assert_panel_fits(self.groups.currentWidget())
            self.assertGreaterEqual(narrow_rows, wide_rows)
            if page_index == 0:
                self.assertGreater(narrow_rows, wide_rows)

    def test_shorter_active_page_returns_height_to_canvas(self):
        self.window.resize(1366, 800)
        self.groups.setCurrentIndex(0)
        self.settle()
        initial_toolbar = self.groups.height()
        initial_canvas = self.window.plot_canvas.height()
        self.groups.setCurrentIndex(1)
        self.settle()
        self.assertLess(self.groups.height(), initial_toolbar)
        self.assertGreater(self.window.plot_canvas.height(), initial_canvas)
        self.assertTrue(self.groups.widget(0).isHidden())
        self.groups.setCurrentIndex(0)
        self.settle()
        self.assertEqual(self.groups.height(), initial_toolbar)

    def test_order_state_and_common_controls_survive_reflow(self):
        self.window.btn_hold.setChecked(True)
        for active in (0, 1, 0):
            self.groups.setCurrentIndex(active)
            key = 'plotting' if active == 0 else 'isar'
            controls = self.window._plot_controls_by_tab[key]
            for index in (active, 2):
                self.groups.setCurrentIndex(index)
                self.window.resize(1200 if index else 1920, 800)
                self.settle()
                page = self.groups.widget(index)
                roles = [role for row in PLOTTING_CONTROL_GROUPS[index][1] for role in row]
                expected = [controls.get(role) or self.window._unavailable_plot_controls[role] for role in roles]
                actual = [page.flow.itemAt(i).widget() for i in range(page.flow.count())]
                self.assertEqual(actual, expected)
                for role in ('auto_plot', 'auto_scale', 'clear'):
                    self.assertTrue(controls[role].isVisible())
                    self.assertTrue(self.groups.header.isAncestorOf(controls[role]))
                self.assertTrue(self.window.chk_plot_legend.isVisible())
                self.assertEqual(self.window._active_plot_tab, key)
        self.assertTrue(self.window.btn_hold.isChecked())

    def test_header_common_controls_wrap_on_narrow_container(self):
        # A narrow plot area must not truncate the common controls as a
        # QTabWidget corner widget would. Test below the full app's minimum.
        host = QWidget()
        layout = QVBoxLayout(host)
        tabs = ResponsiveControlTabs()
        layout.addWidget(tabs)
        layout.addWidget(QWidget(), 1)
        tabs.addTab(ResponsiveButtonPanel(), "Plots")
        tabs.addTab(ResponsiveButtonPanel(), "Plot Manipulation")
        for label in ("Legend", "Auto Plot", "Auto Scale", "Hold", "Clear"):
            tabs.addCommonWidget(QToolButton(text=label))
        try:
            host.resize(340, 600)
            host.show()
            self.settle()
            self.assertGreater(self.assert_panel_fits(tabs.header), 1)
            narrow_height = tabs.height()
            host.resize(1400, 600)
            self.settle()
            self.assertLess(tabs.height(), narrow_height)
        finally:
            host.hide()
            host.deleteLater()


if __name__ == "__main__":
    unittest.main()
