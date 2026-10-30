"""October 17 input audit: region labels, self-touching chains, open dielectrics, sweeps.

Each test reproduces an input the previous code accepted and solved wrongly
(or built drifting sweep values for) and asserts the fix.
"""
from pathlib import Path
import math
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.twod import geometry as g
from ghost_backend.geometry import io as gio

DIELECTRICS = [["1", "4.0", "-0.4", "1.0", "0.0"], ["2", "9.0", "-0.9", "1.0", "0.0"]]


def _pairs(points):
    return [dict(x1=float(a[0]), y1=float(a[1]), x2=float(b[0]), y2=float(b[1]))
            for a, b in zip(points[:-1], points[1:])]


def _segment(name, points, seg_type=2, pos=0, neg=0):
    return dict(name=name, seg_type=seg_type,
                properties=[str(seg_type), "0", "0", str(pos), str(neg)],
                point_pairs=_pairs(points))


def _snapshot(segments):
    return dict(segments=list(segments), ibcs=[], dielectrics=[list(r) for r in DIELECTRICS])


def _circle(radius, count, cw=True):
    theta = np.linspace(0.0, (-2.0 if cw else 2.0) * np.pi, count + 1)
    points = list(zip(radius * np.cos(theta), radius * np.sin(theta)))
    points[-1] = points[0]
    return points


def _errors(snapshot):
    chains = gio.chains_from_snapshot_segments(snapshot["segments"])
    return [m for severity, _, m in gio.check_orientation_consistency(chains) if severity == "ERROR"]


def _validate(snapshot):
    with tempfile.TemporaryDirectory() as directory:
        return g.validate_geometry_snapshot_for_solver(snapshot, base_dir=directory, meters_scale=1.0)


def _coated(inner_type, inner_cw, pos, neg=0):
    return _snapshot([_segment("o", _circle(0.1, 64), 3, 1),
                      _segment("i", _circle(0.07, 48, inner_cw), inner_type, pos, neg)])


class EnclosingMediumTests(unittest.TestCase):

    def test_type4_core_in_another_dielectric_is_rejected(self):
        # pos_mat=2 inside a mat-1 shell solved -5.93/-9.94 dB (no PEC core)
        # instead of the coated -4.70/-7.82 dB.
        self.assertEqual(_errors(_coated(4, True, 1)), [])
        errors = _errors(_coated(4, True, 2))
        self.assertEqual(len(errors), 1)
        self.assertIn("pos_mat=2", errors[0])
        self.assertIn("dielectric 1 around it", errors[0])
        with self.assertRaisesRegex(ValueError, "Set pos_mat to 1"):
            _validate(_coated(4, True, 2))

    def test_type5_swapped_labels_are_rejected(self):
        # Swapped labels changed a two-layer cylinder by 10-21 dB unflagged.
        self.assertEqual(_errors(_coated(5, True, 1, 2)), [])
        self.assertEqual(_errors(_coated(5, False, 2, 1)), [])
        for cw, pos, neg in ((True, 2, 1), (False, 1, 2)):
            errors = _errors(_coated(5, cw, pos, neg))
            self.assertEqual(len(errors), 1, (cw, pos, neg))
            self.assertIn("swap its pos_mat and neg_mat", errors[0])
            with self.assertRaisesRegex(ValueError, "Geometry orientation check failed"):
                _validate(_coated(5, cw, pos, neg))

    def test_type5_outside_label_naming_a_third_medium_is_rejected(self):
        snapshot = _snapshot([_segment("o", _circle(0.1, 64), 3, 1),
                              _segment("m", _circle(0.08, 56), 5, 1, 2),
                              _segment("i", _circle(0.05, 48), 5, 1, 3)])
        errors = _errors(snapshot)
        self.assertEqual(len(errors), 1)
        self.assertIn("'m' puts dielectric 2 around it", errors[0])

    def test_type4_in_open_air_is_rejected(self):
        errors = _errors(_snapshot([_segment("i", _circle(0.07, 48), 4, 1)]))
        self.assertEqual(len(errors), 1)
        self.assertIn("unbounded air", errors[0])

    def test_open_walls_between_contour_and_parent_skip_the_inference(self):
        # The outer shell stitched from two open TYPE 3 halves: the medium
        # around the core is set by open walls, so no inference is made.
        outer = _circle(0.1, 64)
        snapshot = _snapshot([_segment("a", outer[:33], 3, 1), _segment("b", outer[32:], 3, 1),
                              _segment("i", _circle(0.07, 48), 4, 1)])
        self.assertEqual(_errors(snapshot), [])


class SelfTouchingChainTests(unittest.TestCase):
    S = 0.1
    LEFT = [(0.0, 0.0), (-S, -S), (-S, S), (0.0, 0.0)]     # CW
    RIGHT = [(0.0, 0.0), (S, S), (S, -S), (0.0, 0.0)]      # CW

    def test_bow_tie_in_one_segment_is_rejected(self):
        # An inverted lobe cancelled the area (TYPE 3 solved +10.6 dB
        # instead of -8.2 dB) and the winding check never ran.
        for seg_type, pos in ((2, 0), (3, 1)):
            for left in (self.LEFT, self.LEFT[::-1]):
                snapshot = _snapshot([_segment("c", left + self.RIGHT[1:], seg_type, pos)])
                errors = _errors(snapshot)
                self.assertEqual(len(errors), 1)
                self.assertIn("passes through the vertex (0, 0) twice", errors[0])

    def test_lobes_as_separate_segments_still_pass(self):
        snapshot = _snapshot([_segment("L", self.LEFT, 3, 1), _segment("R", self.RIGHT, 3, 1)])
        self.assertEqual(_errors(snapshot), [])

    def test_figure_eight_through_a_vertex_is_rejected(self):
        t = np.linspace(0.0, 2.0 * math.pi, 65)
        points = list(zip(0.1 * np.sin(2 * t), 0.1 * np.sin(t)))
        points[-1] = points[0]
        self.assertTrue(any("twice" in m for m in _errors(_snapshot([_segment("c", points, 2)]))))


class OpenDielectricTests(unittest.TestCase):

    def test_open_type3_contour_is_an_error_in_2d(self):
        # One primitive of 64 missing: previously a warning and 0.3-0.5 dB off.
        snapshot = _snapshot([_segment("c", _circle(0.1, 64)[:-1], 3, 1)])
        # The 2-D preflight's region check names both free ends; the mesher
        # keeps its own refusal as a backstop.
        with self.assertRaisesRegex(ValueError, r"Open material boundary: .*'c' \(TYPE 3\) ends at "
                                    r"\(0.0995185, 0.00980171\) and \(0.1, 0\)"):
            _validate(snapshot)
        with self.assertRaisesRegex(ValueError, "Open dielectric boundary: TYPE 3 segment 'c'"):
            g._build_panels(snapshot, 1.0, 0.3)

    def test_closed_and_stitched_dielectrics_and_open_sheets_still_mesh(self):
        circle = _circle(0.1, 64)
        for segments in (
                [_segment("c", circle, 3, 1)],
                [_segment("a", circle[:33], 3, 1), _segment("b", circle[32:], 3, 1)],
                [_segment("sheet", [(0.0, 0.0), (0.1, 0.0), (0.2, 0.05)], 1)]):
            self.assertTrue(g._build_panels(_snapshot(segments), 1.0, 0.3))


class SweepTests(unittest.TestCase):

    @staticmethod
    def sweep(*args, **kwargs):
        from ghost_backend.ui.solver import SolverTab
        return SolverTab._parse_sweep(None, *args, **kwargs)

    def test_values_do_not_drift(self):
        values = self.sweep("8", "12", "0.001", "Frequencies")
        self.assertEqual(len(values), 4001)
        self.assertEqual(values[-1], 12.0)
        self.assertEqual(values[1234], 9.234)
        self.assertEqual(self.sweep("2", "3", "0.1", "F"), [round(2 + 0.1 * i, 12) for i in range(11)])
        self.assertEqual(self.sweep("10", "0", "2.5", "F"), [10.0, 7.5, 5.0, 2.5, 0.0])

    def test_non_dividing_step_keeps_stop_and_notes_it(self):
        class Owner:
            pass
        owner = Owner()
        from ghost_backend.ui.solver import SolverTab
        with self.assertLogs("ghost_backend.ui.solver", level="WARNING"):
            values = SolverTab._parse_sweep(owner, "0", "10", "3", "Azimuths")
        self.assertEqual(values, [0.0, 3.0, 6.0, 9.0, 10.0])
        self.assertEqual(len(owner._sweep_notes), 1)
        self.assertIn("does not divide", owner._sweep_notes[0])

    def test_full_circle_azimuth_keeps_both_endpoints(self):
        self.assertEqual(self.sweep("0", "360", "90", "Azimuths"),
                         [0.0, 90.0, 180.0, 270.0, 360.0])


class BorGenericExportFrameTests(unittest.TestCase):

    def _result(self, solver):
        row = dict(frequency_ghz=1., theta_inc_deg=20., theta_scat_deg=20., rcs_amp_real=1.,
                   rcs_amp_imag=.5, rcs_linear=4. * np.pi * 1.25)
        quantity, unit = (('sigma_3d', 'dBsm') if solver == 'bor_mom_rcs' else ('sigma_2d', 'dBke'))
        if quantity == 'sigma_2d':
            row['rcs_linear'] = 1.25 / (4. * 2. * np.pi / (299792458.0 / 1e9))     # |A|^2/(4 k0)
        return dict(solver=solver, scattering_mode='monostatic', polarization='VV',
                    rcs_linear_quantity=quantity, rcs_log_unit=unit, samples=[row])

    def test_bor_files_declare_the_aspect_axis_and_keep_arrays(self):
        # Driver BoR files wrote the aspect from the rotation axis as azimuth
        # with no frame metadata.
        from ghost_backend.io import grim
        with tempfile.TemporaryDirectory() as directory:
            [path] = grim.export_result_to_grim(self._result('bor_mom_rcs'), str(Path(directory) / 'bor'))
            with grim.load_grim_npz(path) as stored:
                self.assertIn('NOT radar azimuth', str(stored['pattern_frame_convention']))
                self.assertEqual(str(stored['time_convention']), 'exp(+jwt)')
                np.testing.assert_array_equal(stored['azimuths'], [20.0])
                np.testing.assert_array_equal(stored['elevations'], [0.0])
            [path] = grim.export_result_to_grim(self._result('mom_2d'), str(Path(directory) / 'twod'))
            with grim.load_grim_npz(path) as stored:
                self.assertNotIn('pattern_frame_convention', stored.files)


if __name__ == "__main__":
    unittest.main()
