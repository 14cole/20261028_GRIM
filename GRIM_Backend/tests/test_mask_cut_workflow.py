"""Mask cuts publish radar datasets from the current plotted image."""
import os
import time
from types import SimpleNamespace
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import numpy as np
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QLineEdit
from matplotlib.widgets import PolygonSelector
import test_gui_shell as shell
from test_isar_improvements import grid, params
from GRIM_Backend.plotting.modes.isar_mode import form_isar
from GRIM_Backend.isar.masking import image_from_band, reconstruct_radar, MaskImage
from GRIM_Backend.ui.mask_cut import open_mask_cut
from GRIM_Backend.ui.dataset_actions import DATASET_DIRTY_ROLE


class MaskCutWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.source = grid(az=np.linspace(-5, 5, 17), freq=np.linspace(9e9, 11e9, 17))
        bands, _ = form_isar(cls.source, reconstruction='accurate', window='Rectangular', retain_complex=True)
        cls.image = image_from_band(bands[0], params(cls.source))

    def setUp(self):
        shell.UnifiedGuiShellTest.setUp(self)
        self.dialogs = []
        import copy
        self.image = copy.copy(self.image)
        self.image.metadata = copy.deepcopy(self.image.metadata)
        source_id = self.window._add_dataset_row(self.source, 'Source', 'Loaded')
        self.image.metadata.update(source_dataset_id=source_id, source_dataset_name='Source')
        self.window._show_isar_workspace()
        self.window.show()
        self.attach(self.window.plot_ax, self.image)

    def tearDown(self):
        for dialog in self.dialogs:
            dialog.close()
        self.app.processEvents()
        shell.UnifiedGuiShellTest.tearDown(self)

    def attach(self, axes, image):
        artist = axes.imshow(20 * np.log10(np.maximum(image.magnitude.T, 1e-6)),
                             vmin=-60, vmax=0, origin="lower",
                             extent=(image.x.min(), image.x.max(), image.y.min(), image.y.max()))
        artist._grim_mask_source = image

    def wait(self, dialog):
        deadline = time.monotonic() + 10
        while (dialog.runner.busy or getattr(self.window, '_isar_busy', False)) and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.01)
        self.assertFalse(dialog.runner.busy)
        self.assertFalse(getattr(self.window, '_isar_busy', False))
        self.app.processEvents()

    def open(self):
        dialog = open_mask_cut(self.window)
        self.dialogs.append(dialog)
        dialog.show()
        self.wait(dialog)
        return dialog

    def boundary(self, dialog):
        x, y = self.image.x, self.image.y
        vertices = [(x.min(), y.min()), (0., y.min()), (0., y.max()), (x.min(), y.max())]
        dialog._polygon(vertices)
        return vertices

    def result(self, row):
        item = self.window.table.item(row, 0)
        self.assertTrue(item.data(DATASET_DIRTY_ROLE))
        return item.data(Qt.UserRole)

    def test_polygon_default_and_finish_exports_include_and_exclude(self):
        original = self.source.rcs.copy()
        dialog = self.open()
        self.assertIs(dialog._current(), self.image)
        self.assertEqual(dialog.shape.currentText(), 'Polygon')
        self.assertIsInstance(dialog.selector, PolygonSelector)
        labels = [b.text() for b in dialog.findChildren(QPushButton)]
        self.assertEqual(set(labels), {'Finish Cut', 'Create comparison set', 'Close', 'Load Mask…', 'Save Mask…'})
        self.assertFalse(hasattr(dialog, 'source'))
        self.assertEqual(dialog.findChildren(QLineEdit), [])
        for operation in (0, 1):
            dialog = self.open()
            self.boundary(dialog)
            dialog.operation.setCurrentIndex(operation)
            from unittest.mock import patch
            with patch.object(self.window, '_plot_isar_image') as plot:
                dialog.finish.click()
                self.wait(dialog)
                plot.assert_called_once()
            self.assertEqual(self.window.table.rowCount(), operation + 2, dialog.message.text())
            self.assertTrue(dialog.isHidden())
            self.assertIsNone(dialog.selector)
            self.assertEqual([i.row() for i in self.window.table.selectionModel().selectedRows()], [operation + 1])
            self.assertEqual(self.window.table.item(operation + 1, 0).text(),
                             'Source_include' if operation == 0 else 'Source_exclude')
        inside, outside = self.result(1), self.result(2)
        baseline = reconstruct_radar(self.image)
        np.testing.assert_allclose(inside.rcs + outside.rcs, baseline.rcs, atol=2e-6, rtol=2e-5)
        np.testing.assert_array_equal(inside.azimuths, self.source.azimuths)
        np.testing.assert_array_equal(inside.frequencies, self.source.frequencies)
        np.testing.assert_array_equal(self.source.rcs, original)
        self.assertIsNone(dialog._current())

    def test_comparison_adds_exactly_two_complementary_datasets(self):
        dialog = self.open()
        self.boundary(dialog)
        dialog.comparison.click()
        self.wait(dialog)
        self.assertEqual(self.window.table.rowCount(), 3, dialog.message.text())
        self.assertEqual(self.window.table.item(1, 0).text(), 'Source_include')
        self.assertEqual(self.window.table.item(2, 0).text(), 'Source_exclude')
        self.assertTrue(dialog.isHidden())
        self.assertEqual(sorted(i.row() for i in self.window.table.selectionModel().selectedRows()), [1, 2])
        np.testing.assert_allclose(self.result(1).rcs + self.result(2).rcs,
                                   reconstruct_radar(self.image).rcs, atol=2e-6, rtol=2e-5)

    def test_save_load_mask_restores_visible_boundary_and_operation_then_exports(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        panel = self.open()
        vertices = self.boundary(panel)
        panel.operation.setCurrentIndex(1)
        with TemporaryDirectory() as folder:
            path = str(Path(folder)/'reusable.csv')
            with patch('GRIM_Backend.ui.mask_cut.QFileDialog.getSaveFileName', return_value=(path, '')):
                panel.save_button.click()
            self.assertTrue(Path(path).exists(), panel.message.text())
            panel._polygon([(1,1), (2,1), (2,2)])
            panel.operation.setCurrentIndex(0)
            with patch('GRIM_Backend.ui.mask_cut.QFileDialog.getOpenFileName', return_value=(path, '')):
                panel.load_button.click()
            np.testing.assert_allclose(panel.vertices, vertices)
            np.testing.assert_allclose(panel.selector.verts, vertices)
            self.assertEqual(panel.operation.currentIndex(), 1)
            self.assertTrue(panel.selector.get_visible())
            self.assertTrue(panel.finish.isEnabled())
            self.assertTrue(panel.save_button.isEnabled())
            self.assertIsNotNone(panel._mask_definition)
            panel.comparison.click()
            self.wait(panel)
            self.assertEqual(self.window.table.rowCount(), 3, panel.message.text())
            self.assertEqual(sorted(i.row() for i in self.window.table.selectionModel().selectedRows()), [1,2])

    def test_saved_mask_loads_as_overlay_without_units_dialog(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from GRIM_Backend.isar.mask_geometry import save_mask
        panel = self.open()
        vertices = self.boundary(panel)
        axes = panel.ax
        axes.set_xlabel('Cross-Range (m)')
        axes.set_ylabel('Range (m)')
        with TemporaryDirectory() as folder:
            path = str(Path(folder)/'region.csv')
            save_mask(path, self.image, vertices)
            panel.deactivate()
            overlays = self.window.spatial_overlays
            overlays.refresh()
            with patch('GRIM_Backend.ui.spatial_overlays.QFileDialog.getOpenFileName', return_value=(path, '')), \
                 patch('GRIM_Backend.ui.spatial_overlays.QDialog.exec', side_effect=AssertionError('Unexpected unit prompt')), \
                 patch.object(overlays, 'add_points', wraps=overlays.add_points) as add:
                overlays.load_file()
            self.assertEqual(add.call_count, 1)
            np.testing.assert_allclose(add.call_args.args[0], np.vstack((vertices, vertices[0])))

    def test_invalid_saved_mask_preserves_current_boundary_and_publishes_nothing(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        panel = self.open()
        vertices = self.boundary(panel)
        with TemporaryDirectory() as folder:
            path = Path(folder)/'bad.csv'
            path.write_text('# GRIM-MASK {broken}\nx,y\n0,0\n1,0\n0,1')
            with patch('GRIM_Backend.ui.mask_cut.QFileDialog.getOpenFileName', return_value=(str(path), '')):
                panel.load_button.click()
        np.testing.assert_allclose(panel.vertices, vertices)
        self.assertIn('Could not load mask', panel.message.text())
        self.assertEqual(self.window.table.rowCount(), 1)

    def test_unsupported_image_cannot_publish_image_only_result(self):
        self.window.plot_figure.clear()
        axes = self.window.plot_figure.add_subplot(111)
        image = MaskImage('Composite', self.image.x, self.image.y, self.image.magnitude,
                          metadata={'kind': 'composite'})
        self.attach(axes, image)
        dialog = self.open()
        self.assertIsNone(dialog._current())
        self.assertFalse(dialog.finish.isEnabled())
        self.assertFalse(dialog.comparison.isEnabled())
        self.assertIn('Composite', dialog.details.text())
        self.assertEqual(self.window.table.rowCount(), 1)

    def test_multiple_panels_use_the_clicked_image(self):
        self.window.plot_figure.clear()
        left, right = self.window.plot_figure.subplots(1, 2)
        self.attach(left, self.image)
        self.attach(right, self.image)
        dialog = self.open()
        self.assertIsNone(dialog._current())
        self.assertIn('Click the image panel', dialog.details.text())
        dialog._pick_source(SimpleNamespace(inaxes=right, button=1, xdata=0., ydata=0.))
        self.wait(dialog)
        self.assertIs(dialog._current(), self.image)
        self.assertIsInstance(dialog.selector, PolygonSelector)

    def test_draws_on_existing_canvas_and_close_removes_only_selection(self):
        from matplotlib.backend_bases import MouseEvent
        w = self.window
        canvas, figure, axes = w.plot_canvas, w.plot_figure, w.plot_ax
        image_artist = axes.images[0]
        original_limits = axes.get_xlim(), axes.get_ylim()
        original_lines = len(axes.lines)
        panel = self.open()
        self.assertFalse(panel.isWindow())
        self.assertIs(panel.canvas, canvas)
        self.assertIs(panel.figure, figure)
        self.assertIs(panel.selector.ax, axes)
        canvas.draw()
        vertices = [(-.3, -.3), (.3, -.3), (.3, .3), (-.3, .3)]
        for point in vertices + [vertices[0]]:
            x, y = axes.transData.transform(point)
            for kind in ('motion_notify_event', 'button_press_event', 'button_release_event'):
                event = MouseEvent(kind, canvas, x, y, button=1)
                canvas.callbacks.process(kind, event)
        self.assertTrue(panel.finish.isEnabled())
        self.assertEqual(len(panel.vertices), 4)
        self.assertEqual((axes.get_xlim(), axes.get_ylim()), original_limits)
        panel.close_button.click()
        self.assertTrue(panel.isHidden(), panel.message.text())
        self.assertIsNone(panel.selector)
        self.assertEqual(len(axes.lines), original_lines)
        self.assertIs(axes.images[0], image_artist)
        self.assertIs(w.plot_canvas, canvas)

    def test_switching_views_and_navigation_stop_mask_interaction(self):
        panel = self.open()
        self.window.plot_control_tabs.setCurrentIndex(0)
        self.assertTrue(panel.isHidden(), panel.message.text())
        self.assertIsNone(panel.selector)
        self.window.plot_control_tabs.setCurrentIndex(1)
        panel = self.open()
        self.window.btn_pan.setChecked(True)
        self.assertTrue(panel.isHidden(), panel.message.text())
        panel = self.open()
        self.assertFalse(self.window.btn_pan.isChecked())
        self.window._clear_plot()
        self.assertTrue(panel.isHidden(), panel.message.text())
        self.assertIsNone(panel.selector)

    def test_close_cancels_pending_export_without_adding_a_dataset(self):
        import threading
        from unittest.mock import patch
        from GRIM_Backend.isar.masking import finish_cut
        panel = self.open()
        self.boundary(panel)
        started, release = threading.Event(), threading.Event()

        def delayed(*args, **kwargs):
            started.set()
            release.wait(5)
            return finish_cut(*args, **kwargs)

        with patch('GRIM_Backend.ui.mask_cut.finish_cut', side_effect=delayed):
            panel.finish.click()
            try:
                self.assertTrue(started.wait(2))
                panel.close_button.click()
            finally:
                release.set()
            self.wait(panel)
        self.assertEqual(self.window.table.rowCount(), 1)
        self.assertTrue(panel.isHidden(), panel.message.text())
        self.assertIsNone(panel.selector)

    def test_real_isar_mouse_clicks_leave_a_visible_polygon_and_name_the_plotted_source(self):
        w = self.window
        w.table.selectRow(0)
        for box in (w.list_freq, w.list_az, w.list_elev, w.list_pol):
            box.selectAll()
        w._plot_isar_image()
        deadline = time.monotonic() + 15
        while getattr(w, '_isar_busy', False) and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.01)
        self.assertFalse(getattr(w, '_isar_busy', False))
        # Selection may change after plotting; use the image's source identity.
        w._add_dataset_row(self.source, 'Other', 'Loaded')
        w.table.selectRow(1)
        w.table.item(0, 0).setText('Renamed Source')
        panel = open_mask_cut(w)
        self.dialogs.append(panel)
        self.wait(panel)  # The full native source is reconstructed on demand.
        self.assertIsNotNone(panel.selector)
        self.app.processEvents()
        panel.canvas.draw()
        axes, canvas = panel.ax, panel.canvas
        x0, x1 = axes.get_xlim()
        y0, y1 = axes.get_ylim()
        vertices = [(x0 + .2*(x1-x0), y0 + .2*(y1-y0)),
                    (x0 + .7*(x1-x0), y0 + .2*(y1-y0)),
                    (x0 + .7*(x1-x0), y0 + .7*(y1-y0)),
                    (x0 + .2*(x1-x0), y0 + .7*(y1-y0))]
        for point in vertices + [vertices[0]]:
            x, y = axes.transData.transform(point)
            ratio = canvas.device_pixel_ratio
            position = QPoint(round(x / ratio), round((canvas.figure.bbox.height-y) / ratio))
            QTest.mouseMove(canvas, position)
            QTest.mouseClick(canvas, Qt.LeftButton, Qt.NoModifier, position)
            QTest.qWait(25)
        self.assertTrue(panel.finish.isEnabled())
        self.assertEqual(len(panel.vertices), 4)
        canvas.draw()  # A normal full redraw must still paint the boundary.
        pixels = np.asarray(canvas.buffer_rgba())
        gold = ((pixels[..., 0] == 255) & (pixels[..., 1] == 176) & (pixels[..., 2] == 0))
        self.assertGreater(np.count_nonzero(gold), 20)
        panel.finish.click()
        self.wait(panel)
        self.assertEqual(w.table.item(2, 0).text(), 'Renamed Source_include')
        self.assertEqual([i.row() for i in w.table.selectionModel().selectedRows()], [2])
        self.assertTrue(panel.isHidden(), panel.message.text())

    def test_wide_aperture_backprojection_can_draw_export_and_replot(self):
        from test_mask_cut_backprojection import BackprojectionMaskTests
        w = self.window
        source, _ = BackprojectionMaskTests().source()
        w._add_dataset_row(source, 'Wide aperture', 'Loaded')
        w.table.selectRow(1)
        for box in (w.list_freq, w.list_az, w.list_elev):
            box.selectAll()
        w.list_pol.clearSelection()
        w.list_pol.item(0).setSelected(True)
        # This fixture's targets lie outside the automatic unaliased scene.
        w.isar_advanced.scene.setChecked(True)
        w.isar_advanced.x_half.setValue(.25)
        w.isar_advanced.y_half.setValue(.25)
        w._plot_isar_image()
        deadline = time.monotonic() + 15
        while getattr(w, '_isar_busy', False) and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.01)
        self.assertTrue(w._isar_figure_is_current(), w.status.currentMessage())
        panel = self.open()
        self.assertEqual(panel.image.inverse['kind'], 'backprojection')
        self.assertIsNotNone(panel.selector)
        self.assertEqual(panel.canvas.cursor().shape(), Qt.CrossCursor)
        panel.canvas.draw()
        ax, canvas = panel.ax, panel.canvas
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        points = [(x0+.1*(x1-x0), y0+.1*(y1-y0)), (x0+.7*(x1-x0), y0+.1*(y1-y0)),
                  (x0+.7*(x1-x0), y0+.7*(y1-y0)), (x0+.1*(x1-x0), y0+.7*(y1-y0))]
        for point in points+[points[0]]:
            x,y = ax.transData.transform(point)
            ratio = canvas.device_pixel_ratio
            pos = QPoint(round(x/ratio), round((canvas.figure.bbox.height-y)/ratio))
            # Clicks must place/close vertices even without intervening motion events.
            QTest.mouseClick(canvas,Qt.LeftButton,Qt.NoModifier,pos)
            QTest.qWait(20)
        self.assertTrue(panel.finish.isEnabled())
        self.assertEqual(len(panel.vertices),4)
        panel.finish.click()
        self.wait(panel)
        self.assertTrue(panel.isHidden(), panel.message.text())
        self.assertEqual(w.table.item(2,0).text(),'Wide aperture_include')
        self.assertEqual([i.row() for i in w.table.selectionModel().selectedRows()],[2])
        self.assertIs(w.active_dataset,w.table.item(2,0).data(Qt.UserRole))
        self.assertTrue(w._isar_figure_is_current(),w.status.currentMessage())
        self.assertEqual(w._isar_meshes[0]._grim_mask_source.metadata['source_dataset_name'],
                         'Wide aperture_include')
