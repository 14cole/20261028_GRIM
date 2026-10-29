"""Focused regressions for the experimental sparse ISAR reconstruction."""

import unittest

import numpy as np

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.plotting.modes import isar_mode


class TestRemovedSparseMode(unittest.TestCase):
    def test_removed_solver_is_not_exposed(self):
        self.assertFalse(hasattr(isar_mode, '_compute_band_sparse_l1'))


class TestSparseIsarPublicValidation(unittest.TestCase):
    def setUp(self):
        azimuth = np.asarray([-2.0, -1.0, 0.0, 1.0, 2.0])
        frequency = np.asarray([8.0, 8.25, 8.5, 8.75, 9.0])
        self.grid = RcsGrid(
            azimuth,
            [0.0],
            frequency,
            ["VV"],
            rcs=np.ones((5, 1, 5, 1), dtype=np.complex64),
            units={
                "azimuth": "deg",
                "elevation": "deg",
                "frequency": "GHz",
                "angular_coordinate_system": "conic",
                "time_convention": "exp(+jwt)",
            },
            extra={
                "phase_reference": "fixed origin",
                "measurement_geometry": "far-field monostatic",
                "motion_compensation": "stable",
                "range_phase_convention": "S~exp(-j*2*k*R)",
            },
        )

    def test_unknown_window_is_not_silently_hanning(self):
        with self.assertRaisesRegex(ValueError, "unsupported ISAR window"):
            isar_mode.form_isar(self.grid, window="Hannig")
        self.assertEqual(
            isar_mode._window_name("Kaiser beta=15"), "Kaiser β=15"
        )

    def test_unknown_length_unit_is_not_silently_meters(self):
        for invalid_unit in ("yards", "", None):
            with self.subTest(length_unit=invalid_unit):
                with self.assertRaisesRegex(ValueError, "unsupported ISAR length unit"):
                    isar_mode.form_isar(self.grid, length_unit=invalid_unit)

    def test_invalid_sparse_controls_are_rejected_without_coercion(self):
        invalid_cases = (
            ({"l1_strength": 0.0}, "l1_strength"),
            ({"l1_strength": 1.0}, "l1_strength"),
            ({"l1_strength": float("nan")}, "l1_strength"),
            ({"l1_iterations": True}, "l1_iterations"),
            ({"l1_iterations": 9}, "l1_iterations"),
            ({"l1_iterations": 10.5}, "l1_iterations"),
            ({"l1_iterations": 10_001}, "l1_iterations"),
        )
        for options, message in invalid_cases:
            with self.subTest(options=options):
                with self.assertRaisesRegex(TypeError, message):
                    isar_mode.form_isar(self.grid, **options)

    def test_removed_sparse_mode_rejected_explicitly(self):
        with self.assertRaisesRegex(ValueError, "reconstruction must be"):
            isar_mode.form_isar(self.grid, reconstruction='sparse')


if __name__ == "__main__":
    unittest.main(verbosity=2)
