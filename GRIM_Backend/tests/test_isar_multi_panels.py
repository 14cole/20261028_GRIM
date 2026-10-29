"""Multi-dataset ISAR/composite panels preserve physical selections and sources."""
import os
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import numpy as np
from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtWidgets import QApplication
import test_gui_shell as shell
from test_isar_improvements import grid
from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.ui.mask_cut import open_mask_cut
from GRIM_Backend.scripting.plotting import plot_datasets


class MultiIsarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        shell.UnifiedGuiShellTest.setUp(self)
        w = self.window
        template = grid(az=np.linspace(-5, 5, 9), freq=np.linspace(9, 11, 9), unit='GHz')
        data = np.ones((9, 2, 9, 2), np.complex64)
        data[:, 1] *= 2
        data[..., 1] *= 3
        self.first = RcsGrid(template.azimuths, [0, 20], template.frequencies, ['VV', 'HH'],
                             rcs=data, units=template.units, extra=template.extra)
        self.second = RcsGrid(np.deg2rad(template.azimuths), np.deg2rad([0, 20]),
                              template.frequencies*1e9, ['VV', 'HH'], rcs=data*.5,
                              units=dict(template.units, frequency='Hz', azimuth='rad', elevation='rad'),
                              extra=template.extra)
        for source, name in ((self.first, 'Original'), (self.second, 'Cut')):
            w._add_dataset_row(source, name, 'Loaded')
        self.first = w.table.item(0, 0).data(Qt.UserRole)
        self.second = w.table.item(1, 0).data(Qt.UserRole)
        w.table.selectRow(0)
        w.table.selectionModel().select(w.table.model().index(1, 0),
                                       QItemSelectionModel.Select | QItemSelectionModel.Rows)
        w.table.setCurrentItem(w.table.item(0, 0), QItemSelectionModel.NoUpdate)
        w._on_dataset_selection_changed()
        w._show_isar_workspace()
        for listing in (w.list_pol, w.list_elev, w.list_freq, w.list_az):
            listing.selectAll()
        w.resize(1800, 1400)
        w.show()

    def tearDown(self):
        shell.UnifiedGuiShellTest.tearDown(self)

    def wait(self):
        deadline = time.monotonic() + 20
        while self.window._isar_busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.01)
        self.app.processEvents()
        self.assertFalse(self.window._isar_busy)
        self.assertTrue(self.window._isar_figure_is_current(), self.window.status.currentMessage())

    def test_isar_panels_map_units_keep_sources_and_replay(self):
        w = self.window
        w.chk_isar_freq_band.setChecked(True)
        w.spin_isar_freq_min.setValue(9.25)
        w.spin_isar_freq_max.setValue(10.75)
        w._plot_isar_image(composite=False)
        self.wait()
        self.assertEqual(len(w._isar_meshes), 8)
        self.assertIs(w.active_dataset, self.first)
        sources = [mesh._grim_mask_source for mesh in w._isar_meshes]
        self.assertEqual([s.metadata['source_dataset_name'] for s in sources], ['Original']*4+['Cut']*4)
        for source in sources:
            self.assertEqual(len(source.params['freq_hz']), 7)
        self.assertIn('20°', w.plot_axes[1].get_title())
        self.assertIn('HH', w.plot_axes[2].get_title())
        self.assertEqual(len(w.plot_colorbars), 1)
        for axis in w.plot_axes:
            self.assertEqual(axis.xaxis.label.get_color(), w._current_plot_text())
            self.assertEqual(axis.get_facecolor(), w.plot_axes[0].get_facecolor())
        panel = open_mask_cut(w)
        panel._pick_source(SimpleNamespace(inaxes=w.plot_axes[4], button=1, xdata=0., ydata=0.))
        deadline = time.monotonic() + 20
        while panel.runner.busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.01)
        self.assertFalse(panel.runner.busy)
        self.assertEqual(panel.source_name, 'Cut')
        self.assertEqual(panel.image.metadata['source_selection_digest'], sources[4].source_digest)
        panel.deactivate()
        spec = w.last_python_plot_spec
        self.assertEqual(spec[0], 'supported')
        self.assertEqual(len(spec[4]['isar_panels']), 8)
        replay = plot_datasets([('Original', self.first), ('Cut', self.second)], mode=spec[3], **spec[4])
        replay_axes = [ax for ax in replay.axes if ax.images]
        self.assertEqual(len(replay_axes), 8)
        for original, replay_axis in zip(w._isar_meshes, replay_axes):
            np.testing.assert_allclose(original.get_array(), replay_axis.images[0].get_array(), atol=1e-5)

    def test_composite_panels_and_independent_colorbars(self):
        w = self.window
        options = dict(w.isar_advanced.options(), composite_side=64)
        w.chk_colorbar_shared.setChecked(False)
        with patch.object(w.isar_advanced, 'options', return_value=options):
            w._plot_isar_image(composite=True)
        self.wait()
        self.assertEqual(len(w._isar_meshes), 8)
        self.assertEqual(len(w.plot_colorbars), 8)
        self.assertTrue(all(m._grim_mask_source.metadata['kind'] == 'composite' for m in w._isar_meshes))
        self.assertIn('Cut', w.plot_axes[-1].get_title())
        self.assertTrue(all(not m._grim_mask_source.params['retain_complex'] for m in w._isar_meshes))

    def test_panel_limit_rejects_before_submission(self):
        w = self.window
        with patch('GRIM_Backend.plotting.modes.common.MAX_WATERFALL_PANELS', 3), patch.object(w, '_isar_submit') as submit:
            w._plot_isar_image(composite=False)
        submit.assert_not_called()
        self.assertIn('more than 3 panels', w.status.currentMessage())

    def test_changed_multi_selection_discards_pending_result(self):
        import threading
        from GRIM_Backend.plotting.modes import isar_mode
        entered, release = threading.Event(), threading.Event()
        compute = isar_mode.compute_bands

        def delayed(request):
            entered.set()
            release.wait(5)
            return compute(request)

        w = self.window
        with patch.object(isar_mode, 'compute_bands', side_effect=delayed):
            w._plot_isar_image(composite=False)
            self.assertTrue(entered.wait(2))
            try:
                w.table.selectionModel().select(w.table.model().index(1, 0),
                    QItemSelectionModel.Deselect | QItemSelectionModel.Rows)
                self.assertIs(w.active_dataset, self.first)
            finally:
                release.set()
            deadline = time.monotonic() + 10
            while w._isar_busy and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.01)
        self.assertFalse(w._isar_busy)
        self.assertFalse(w._isar_figure_is_current())
        self.assertIn('discarded', w.status.currentMessage())
