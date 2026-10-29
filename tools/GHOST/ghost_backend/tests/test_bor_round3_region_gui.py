"""Geometry fill and captured validation retain the selected coordinate units."""
import os
from pathlib import Path
import sys
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PySide6.QtWidgets import QApplication
from ghost_backend.bor.solver import sphere_generatrix
from ghost_backend.geometry.io import Segment
from ghost_backend.ui.geometry import GeometryTab


def test_region_cache_and_captured_validation_follow_units():
    app = QApplication.instance() or QApplication([])
    tab = GeometryTab()
    try:
        tab.set_geometry_mode("bor")
        points = sphere_generatrix(.06, 12)
        # This positive radius is numerical axis in inches, but not meters.
        # It exercises the physical absolute tolerance without moving vertices.
        points[0, 0] = 2e-12
        tab.segments = [Segment("outer", "3", ["3", "1", "0", "1", "0"],
                                [v for a, b in zip(points[:-1], points[1:]) for v in (a[0], b[0])],
                                [v for a, b in zip(points[:-1], points[1:]) for v in (a[1], b[1])])]
        tab.set_geometry_units("inches")
        inches = tab._current_region_report()
        assert not inches.errors()
        assert tab._current_region_report() is inches
        tab.chk_fill_materials.setChecked(True)
        version = tab._validation_version
        tab.set_geometry_units("meters")
        assert tab._validation_version > version
        assert tab._region_timer.isActive()
        meters = tab._current_region_report()
        assert meters is not inches
        assert meters.closure_failures
        tab.set_geometry_units("inches")
        assert not tab._current_region_report().errors()

        # Capture the audit object without starting a worker or modal dialog.
        with mock.patch("ghost_backend.ui.geometry._GeometryValidationWorker.start"):
            tab.validate_geometry()
        assert tab._validation_worker.audit.meters_scale == .0254
        tab._validation_worker = None
    finally:
        tab.close()
        tab.deleteLater()
        app.processEvents()

