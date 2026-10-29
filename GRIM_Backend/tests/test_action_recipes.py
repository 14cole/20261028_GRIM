"""Recipe capture and actual GUI batch replay, including unsaved inputs."""
import json
import tempfile
import threading
from pathlib import Path
from unittest import mock
import unittest

import numpy as np
from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication, QDialog

from GRIM_Backend.scripting.action_recipe import ActionCapture, ActionRecipe, axis_units
from GRIM_Backend.scripting.recorder import DatasetReference, PythonScriptRecorder
from GRIM_Backend.datasets.transforms import offset_db, flip_phase
from GRIM_Backend.datasets.work_control import WorkCancelled
import test_gui_shell as shell


def step(name, args=(), kwargs=None, kind='function'):
    return dict(kind=kind, name=name, args=list(args), kwargs=kwargs or {})


class RecipeTests(unittest.TestCase):
    def test_unsaved_chain_roundtrip_replays_values_without_changing_input(self):
        source = shell._grid(2)
        before = source.power.copy()
        capture = ActionCapture()
        recorder = PythonScriptRecorder()
        recorder.action_listener = capture.capture
        a, b, c = [DatasetReference(value, value) for value in 'abc']
        capture.start(a, source)
        recorder.record_function(b, 'offset_db', [a], args=(np.float64(6),))
        recorder.record_function(c, 'flip_phase', [b])
        capture.stop()
        recipe = ActionRecipe.loads(capture.recipe.dumps())
        self.assertEqual(len(recipe.steps), 2)
        target = shell._grid(3)
        result = recipe.run(target)
        expected = flip_phase(offset_db(target, 6))
        np.testing.assert_allclose(result.rcs, expected.rcs)
        np.testing.assert_array_equal(source.power, before)
        np.testing.assert_allclose(target.power, shell._grid(3).power)

    def test_rejects_unregistered_actions_and_wrong_units(self):
        source = shell._grid()
        recipe = ActionRecipe('test', axis_units(source), [step('offset_db', [1])])
        altered = json.loads(recipe.dumps())
        altered['steps'][0]['name'] = '__import__'
        with self.assertRaises(ValueError):
            ActionRecipe.loads(json.dumps(altered))
        altered['steps'][0] = step('offset_db', kwargs={'unknown': 1})
        with self.assertRaises(TypeError):
            ActionRecipe.loads(json.dumps(altered))
        target = shell._grid()
        target.units['frequency'] = 'Hz'
        with self.assertRaisesRegex(ValueError, 'Axis units differ'):
            recipe.run(target)

    def test_unsupported_and_branched_actions_stop_capture(self):
        for sources, steps in ((['a', 'b'], [step('offset_db', [1])]),
                               (['b'], [step('offset_db', [1])]),
                               (['a'], None)):
            capture = ActionCapture()
            a, b = DatasetReference('a', 'A'), DatasetReference('b', 'B')
            capture.start(a, shell._grid())
            capture.capture([b], [DatasetReference(s, s) for s in sources], steps, 'Combine')
            self.assertFalse(capture.recording)
            self.assertTrue(capture.error)
            self.assertEqual(capture.recipe.steps, [])

    def test_regrid_wrap_and_round_pipeline_matches_direct_operations(self):
        from test_isar_improvements import grid
        from GRIM_Backend.scripting.action_recipe import regrid_resolved
        source = grid(az=np.linspace(-5, 5, 11), freq=np.linspace(9e9, 11e9, 5))
        recipe = ActionRecipe('test', axis_units(source), [
            step('regrid_resolved', ['azimuth'], dict(start=-4., step=2., count=5)),
            step('wrap_azimuth', ['-180_180'], kind='method'),
            step('round_axes', [2], dict(azimuths=True), kind='method'),
        ])
        result = recipe.run(source)
        expected = regrid_resolved(source, 'azimuth', start=-4., step=2., count=5).wrap_azimuth('-180_180').round_axes(2, azimuths=True)
        np.testing.assert_allclose(result.rcs, expected.rcs)
        np.testing.assert_array_equal(result.azimuths, [-4, -2, 0, 2, 4])
        namespace = dict(dataset=source, np=np, regrid_axis=__import__(
            'GRIM_Backend.datasets.transforms', fromlist=['regrid_axis']).regrid_axis)
        exported = eval(recipe.expression('dataset'), namespace)
        np.testing.assert_allclose(exported.rcs, result.rcs)

    def test_cancellation_is_not_converted_into_a_dataset_failure(self):
        recipe = ActionRecipe('test', axis_units(shell._grid()), [step('offset_db', [1])])
        with mock.patch('GRIM_Backend.scripting.action_recipe.checkpoint', side_effect=WorkCancelled):
            with self.assertRaises(WorkCancelled):
                recipe.run(shell._grid())

    def test_failure_names_step_and_does_not_modify_source(self):
        source = shell._grid(3)
        recipe = ActionRecipe('test', axis_units(source), [
            step('offset_db', [1]), step('crop_dataset', kwargs={'azimuth_range': [10, 20]})])
        with self.assertRaisesRegex(ValueError, r'Step 2 \(Crop / Slice\)'):
            recipe.run(source)
        np.testing.assert_array_equal(source.rcs, shell._grid(3).rcs)


class RecipeGuiTests(unittest.TestCase):
    setUp = shell.UnifiedGuiShellTest.setUp
    tearDown = shell.UnifiedGuiShellTest.tearDown
    _wait_for_background = shell.UnifiedGuiShellTest._wait_for_background

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def select(self, rows):
        table = self.window.table
        table.clearSelection()
        for row in rows:
            table.selectionModel().select(table.model().index(row, 0),
                QItemSelectionModel.Select | QItemSelectionModel.Rows)
        self.app.processEvents()

    def test_record_real_buttons_then_batch_replay_and_load(self):
        w, dialog = self.window, self.window.action_recorder
        w._add_dataset_row(shell._grid(2), 'Example', 'Synthetic', '')
        self.select([0])
        w.btn_record_actions.click()
        dialog.record.click()
        self.assertTrue(dialog.capture.recording)
        with mock.patch('GRIM_Backend.ui.dataset_actions.QInputDialog.getDouble', return_value=(6., True)):
            w.btn_offset.click()
            self._wait_for_background()
        self.assertEqual([i.row() for i in w.table.selectionModel().selectedRows()], [1])
        w.btn_flip_phase.click()
        self._wait_for_background()
        w.btn_record_actions.click()
        self.assertFalse(dialog.capture.recording)
        self.assertEqual([s['name'] for s in dialog.capture.recipe.steps], ['offset_db', 'flip_phase'])
        self.assertEqual(dialog.steps.count(), 2)
        w._add_dataset_row(shell._grid(3), 'Target A', 'Synthetic', '')
        w._add_dataset_row(shell._grid(4), 'Target B', 'Synthetic', '')
        self.select([3, 4])
        dialog.run_selected()
        self._wait_for_background()
        self.assertEqual(w.table.rowCount(), 7)
        from PySide6.QtCore import Qt
        for row, amplitude in ((5, 3), (6, 4)):
            actual = w.table.item(row, 0).data(Qt.UserRole)
            expected = flip_phase(offset_db(shell._grid(amplitude), 6))
            np.testing.assert_allclose(actual.rcs, expected.rcs)
        self.assertIn('Created 2 dataset(s); 0 failed', dialog.message.text())
        with tempfile.TemporaryDirectory() as root:
            path = str(Path(root) / 'recipe.json')
            with mock.patch('GRIM_Backend.ui.action_recorder.QFileDialog.getSaveFileName', return_value=(path, '')):
                dialog.save_recipe()
            self.assertTrue(Path(path).exists(), dialog.message.text())
            self.assertEqual(len(ActionRecipe.loads(Path(path).read_text()).steps), 2)
            dialog.capture.recipe.steps.clear()
            with mock.patch('GRIM_Backend.ui.action_recorder.QFileDialog.getOpenFileName', return_value=(path, '')):
                dialog.load_recipe()
            self.assertEqual(dialog.steps.count(), 2)

    def test_batch_failure_preserves_other_success_and_reports_failed_step(self):
        w, dialog = self.window, self.window.action_recorder
        w._add_dataset_row(shell._grid(2), 'Good', 'Synthetic', '')
        wrong = shell._grid(3)
        wrong.units['frequency'] = 'Hz'
        w._add_dataset_row(wrong, 'Wrong units', 'Synthetic', '')
        dialog.capture.recipe = ActionRecipe('Offset', axis_units(shell._grid()), [step('offset_db', [2])])
        self.select([0, 1])
        dialog.run_selected()
        self._wait_for_background()
        self.assertEqual(w.table.rowCount(), 3)
        self.assertIn('Created 1 dataset(s); 1 failed', dialog.message.text())
        self.assertIn('Wrong units: Axis units differ', dialog.report.toPlainText())

    def test_gui_regrid_wrap_round_recording_matches_demonstration(self):
        from test_isar_improvements import grid
        from PySide6.QtCore import Qt
        w, dialog = self.window, self.window.action_recorder
        source = grid(az=np.linspace(-5, 5, 11), freq=np.linspace(9e9, 11e9, 5))
        w._add_dataset_row(source, 'Example', 'Synthetic', '')
        self.select([0])
        dialog.start_recording()
        for dialog_name, button, parameters in (
            ('RegridDialog', w.btn_interpolate, dict(axis='azimuth', start=-4., stop=4., step=.5, unit='deg')),
            ('WrapDialog', w.btn_wrap, dict(azimuth=True, phase=True, mode='0_360')),
            ('RoundDialog', w.btn_round, dict(azimuths=True, elevations=False, frequencies=False, decimals=2)),
        ):
            with mock.patch('GRIM_Backend.ui.dataset_actions.' + dialog_name) as factory:
                factory.return_value.exec.return_value = QDialog.Accepted
                factory.return_value.get_params.return_value = parameters
                button.click()
                self._wait_for_background()
        dialog.stop_recording()
        self.assertFalse(dialog.capture.error, dialog.capture.error)
        self.assertEqual(len(dialog.capture.recipe.steps), 4)
        replay = ActionRecipe.loads(dialog.capture.recipe.dumps()).run(source)
        demonstrated = w.table.item(3, 0).data(Qt.UserRole)
        np.testing.assert_array_equal(replay.azimuths, demonstrated.azimuths)
        np.testing.assert_allclose(replay.rcs, demonstrated.rcs)

    def test_cancel_replay_publishes_no_partial_datasets(self):
        from GRIM_Backend.datasets.work_control import checkpoint
        w, dialog = self.window, self.window.action_recorder
        w._add_dataset_row(shell._grid(), 'Target', 'Synthetic', '')
        dialog.capture.recipe = ActionRecipe('test', axis_units(shell._grid()), [step('offset_db', [1])])
        self.select([0])
        entered, release = threading.Event(), threading.Event()

        def delayed(dataset, amount):
            entered.set()
            if not release.wait(5):
                raise TimeoutError('Test did not release worker')
            checkpoint()
            return offset_db(dataset, amount)

        with mock.patch.dict('GRIM_Backend.scripting.action_recipe.FUNCTIONS', {'offset_db': delayed}):
            dialog.run_selected()
            try:
                self.assertTrue(entered.wait(2))
                w._cancel_background_job()
            finally:
                release.set()
                self._wait_for_background()
        dialog._update_buttons()
        self.assertEqual(w.table.rowCount(), 1)
        self.assertIn('canceled', dialog.message.text().lower())

    def test_blocked_recipe_is_not_silently_replayed_and_restores_between_sessions(self):
        w, dialog = self.window, self.window.action_recorder
        w._add_dataset_row(shell._grid(), 'Example', 'Synthetic', '')
        self.select([0])
        dialog.capture.recipe = ActionRecipe('Saved', axis_units(shell._grid()), [step('offset_db', [2])])
        dialog.capture.error = 'Recording stopped: Unsupported action.'
        dialog._changed()
        dialog.run_selected()
        self.assertFalse(w._background_job_active())
        self.assertFalse(dialog.run.isEnabled())
        restored = shell._RecordingWindow(settings=self.app_settings)
        try:
            self.assertEqual(len(restored.action_recorder.capture.recipe.steps), 1)
            self.assertEqual(restored.action_recorder.capture.error, dialog.capture.error)
        finally:
            restored.deleteLater()
            self.app.processEvents()
        dialog.keep_steps()
        self.assertTrue(dialog.run.isEnabled())
