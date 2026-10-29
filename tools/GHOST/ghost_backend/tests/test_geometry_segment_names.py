"""Segment names remain labels through GUI, geometry serialization and solver preflight."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ghost_backend.geometry.io import (Segment, parse_geometry, build_geometry_text,
    build_geometry_snapshot, snapshot_to_geometry_text)
from ghost_backend.twod.geometry import validate_geometry_snapshot_for_solver


class SegmentNameTests(unittest.TestCase):
    def test_quoted_name_roundtrip_preserves_type_properties_and_coordinates(self):
        for name in ('left wing', 'Panel 2', 'body: aft #1', 'a "quoted" panel', 'path\\label', 'two  spaces'):
            with self.subTest(name=name):
                segment = Segment(name, '2', ['2', '8', '0', '0', '0'], [0., 1.], [0., 0.])
                encoded = build_geometry_text('Test', [segment], [], [])
                title, segments, ibcs, materials = parse_geometry(encoded)
                self.assertEqual(segments[0], segment)
                snapshot = build_geometry_snapshot(title, segments, ibcs, materials)
                validate_geometry_snapshot_for_solver(snapshot, '.')
                self.assertEqual(snapshot_to_geometry_text(snapshot), encoded)

    def test_unquoted_multiword_names_and_legacy_headers(self):
        for header, name, kind in [('Left wing 2', 'Left wing', '2'),
                                   ('Left wing', 'Left wing', None),
                                   ('nose 2', 'nose', '2'),
                                   ('nose', 'nose', None),
                                   ('"Panel 2"', 'Panel 2', None)]:
            with self.subTest(header=header):
                _, segments, _, _ = parse_geometry('Segment: '+header+'\nproperties: 2 8 0 0 0\n0 0 1 0\n')
                self.assertEqual((segments[0].name, segments[0].seg_type), (name, kind))

    def test_malformed_quoted_headers_are_rejected(self):
        for header in ('"unclosed 2', '"" 2', '"name" trailing words', '"name"2', '"line\\nbreak" 2'):
            with self.subTest(header=header), self.assertRaises(ValueError):
                parse_geometry('Segment: '+header+'\nproperties: 2 8 0 0 0\n0 0 1 0\n')

    def test_gui_load_rename_and_save_space_containing_name(self):
        from PySide6.QtWidgets import QApplication
        from ghost_backend.ui.geometry import GeometryTab
        app = QApplication.instance() or QApplication([])
        tab = GeometryTab()
        try:
            with tempfile.TemporaryDirectory() as directory:
                source, output = Path(directory)/'source.geo', Path(directory)/'saved.geo'
                source.write_text('Segment: Left wing 2\nproperties: 2 8 0 0 0\n0 0 1 0\n')
                with mock.patch('ghost_backend.ui.geometry.QFileDialog.getOpenFileName', return_value=(str(source), '')), \
                     mock.patch('ghost_backend.ui.geometry.QMessageBox.information'):
                    self.assertTrue(tab.load_geo())
                self.assertEqual(tab.table.item(0, 0).text(), 'Left wing')
                tab.table.item(0, 0).setText('Renamed panel 2')
                app.processEvents()
                with mock.patch('ghost_backend.ui.geometry.QFileDialog.getSaveFileName', return_value=(str(output), '')), \
                     mock.patch('ghost_backend.ui.geometry.QMessageBox.information'), \
                     mock.patch('ghost_backend.ui.geometry.QMessageBox.critical') as error:
                    tab.save_geo()
                    error.assert_not_called()
                self.assertTrue(output.exists())
                _, segments, _, _ = parse_geometry(output.read_text())
                self.assertEqual(segments[0].name, 'Renamed panel 2')
                self.assertEqual(segments[0].seg_type, '2')
                self.assertEqual(segments[0].properties, ['2', '8', '0', '0', '0'])
        finally:
            tab.deleteLater()
            app.processEvents()
