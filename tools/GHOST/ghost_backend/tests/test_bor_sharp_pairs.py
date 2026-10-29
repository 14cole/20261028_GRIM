"""Graded polar quadrature of sharp touching BoR element pairs (October 2026).

Thin rims, needle/cone tips and acute coating junctions: the fixed graded
cells had a block error that did not change with the mesh; those pairs use
bor.sharp_pairs, checked on every solve. Since the follow-up every touching
pair does (test_bor_touching_pairs.py); 'acute' and 'thin' remain the
classes reported as sharp.
"""
from pathlib import Path
import math
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.bor import solver as bor, sharp_pairs, geometry as bor_geometry
from ghost_backend.bor.kernels import Generatrix
from ghost_backend.bor.near_parallel import NearTask

WAVELENGTH = 0.3
K = 2.0 * math.pi / WAVELENGTH
FREQUENCY_HZ = 299_792_458.0 / WAVELENGTH
MODES = 8
KINDS = ('efie', 'mfie')


def _rim(angle_degrees, length, radius=0.15):
    """Three elements on each side of a rim at (radius, 0)."""
    half = math.radians(angle_degrees) / 2
    up = [(radius - j * length * math.cos(half), j * length * math.sin(half)) for j in (3, 2, 1)]
    down = [(radius - j * length * math.cos(half), -j * length * math.sin(half)) for j in (1, 2, 3)]
    return Generatrix(np.array(up + [(radius, 0.0)] + down))


def _needle(angle_degrees, length, count=6):
    """A cone from its tip on the axis; ``angle_degrees`` is the included tip angle."""
    half = math.radians(angle_degrees) / 2
    return Generatrix(np.array([(j * length * math.sin(half), -j * length * math.cos(half))
                                for j in range(count + 1)]))


def _lens(angle_degrees, per_side, radius=0.15):
    height = radius * math.tan(math.radians(angle_degrees) / 2)
    up = np.column_stack((np.linspace(0, radius, per_side + 1), np.linspace(height, 0, per_side + 1)))
    down = np.column_stack((np.linspace(radius, 0, per_side + 1), np.linspace(0, -height, per_side + 1)))[1:]
    return np.vstack((up, down))


def _cone(angle_degrees, along, base, length=0.3):
    """Cone of included tip angle ``angle_degrees`` (tip at +length/2) with a flat base."""
    rho = length * math.tan(math.radians(angle_degrees) / 2)
    side = np.column_stack((np.linspace(0, rho, along + 1), np.linspace(length / 2, -length / 2, along + 1)))
    cap = np.column_stack((np.linspace(rho, 0, base + 1), np.full(base + 1, -length / 2)))[1:]
    return np.vstack((side, cap))


def _blocks(gp, e, gq, f, points, k=K, kinds=KINDS):
    return bor._contract_near_points(gp, e, gq, f, k, MODES, kinds, points, signed=False)


def _reference(gen, e, f):
    """The graded rule with 32 points per piece and every graded stop 4x deeper."""
    _, points, ends = sharp_pairs._same_surface_geometry(gen, e, f)
    return sharp_pairs._cached_rule(tuple(points.ravel()), ends, 32, 0.25, 1.0)


def _db(result, key):
    return 10.0 * np.log10(np.asarray(result[key]))


class SharpPairElementTests(unittest.TestCase):
    def test_rim_blocks_converge_where_the_cell_rule_is_mesh_independent(self):
        for angle in (15.0, 5.0, 1.0):
            errors = []
            for elements in (10, 80):
                gen = _rim(angle, WAVELENGTH / elements)
                reference = _blocks(gen, 2, gen, 3, _reference(gen, 2, 3))
                production = _blocks(gen, 2, gen, 3, bor._same_surface_points(gen, 2, 3, KINDS, 4, MODES))
                cells = _blocks(gen, 2, gen, 3, bor._cell_points('corner10', depth=4))
                self.assertLess(sharp_pairs.relative_change(production, reference), 1e-6)
                errors.append(sharp_pairs.relative_change(cells, reference))
            # The fixed cells' error is a property of the angle, not the mesh.
            self.assertGreater(min(errors), 2e-2)
            self.assertLess(abs(math.log(errors[0] / errors[1])), math.log(1.5))

    def test_needle_blocks_converge(self):
        for angle in (10.0, 2.0, 0.5):
            gen = _needle(angle, WAVELENGTH / 40)
            for e, f in ((0, 0), (3, 3), (0, 1), (4, 3)):
                with self.subTest(angle=angle, pair=(e, f)):
                    self.assertEqual(sharp_pairs.same_surface_pair(gen, e, f)[0], 'thin')
                    reference = _blocks(gen, e, gen, f, _reference(gen, e, f))
                    production = _blocks(gen, e, gen, f, bor._same_surface_points(gen, e, f, KINDS, 4, MODES))
                    self.assertLess(sharp_pairs.relative_change(production, reference), 1e-6)
        # The fixed cells were 33% off on the fourth element of a 2 degree needle.
        gen = _needle(2.0, WAVELENGTH / 40)
        cells = _blocks(gen, 3, gen, 3, bor._cell_points('diag', depth=4))
        self.assertGreater(sharp_pairs.relative_change(cells, _blocks(gen, 3, gen, 3, _reference(gen, 3, 3))), 0.1)

    def test_tip_blocks_do_not_depend_on_axial_position(self):
        # Absolute z samples lost 2e-5 of a 0.25 degree tip block 0.15 m from z = 0.
        half, length = math.radians(0.125), WAVELENGTH / 80
        blocks = []
        for z0 in (0.0, 0.15, 1.5):
            gen = Generatrix(np.array([(j * length * math.sin(half), z0 - j * length * math.cos(half))
                                       for j in range(5)]))
            blocks.append(_blocks(gen, 0, gen, 0, bor._same_surface_points(gen, 0, 0, KINDS, 4, MODES)))
            if z0 == 1.5:
                self.assertLess(sharp_pairs.relative_change(blocks[-1], _blocks(gen, 0, gen, 0, _reference(gen, 0, 0))), 1e-6)
        for other in blocks[1:]:
            self.assertLess(sharp_pairs.relative_change(other, blocks[0]), 1e-9)

    def test_high_modes_grade_the_ring_scale_deeper(self):
        gen = _needle(2.0, WAVELENGTH / 40)
        modes = 60
        _, points, ends = sharp_pairs._same_surface_geometry(gen, 3, 3)
        reference = bor._contract_near_points(gen, 3, gen, 3, K, modes, KINDS, sharp_pairs._cached_rule(
            tuple(points.ravel()), ends, 32, 1 / 64, 1.0), signed=False)
        production = bor._contract_near_points(gen, 3, gen, 3, K, modes, KINDS,
                                               bor._same_surface_points(gen, 3, 3, KINDS, 4, modes), signed=False)
        self.assertLess(sharp_pairs.relative_change(production, reference), 1e-6)

    def test_adjacent_rule_is_reciprocal(self):
        for gen, e in ((_rim(5.0, WAVELENGTH / 40), 2), (_needle(2.0, WAVELENGTH / 40), 2)):
            forward = _blocks(gen, e, gen, e + 1, bor._same_surface_points(gen, e, e + 1, KINDS, 4))['efie']
            reverse = _blocks(gen, e + 1, gen, e, bor._same_surface_points(gen, e + 1, e, KINDS, 4))['efie']
            # tt(e, f) = tt(f, e)^T, ff likewise, tf(e, f) = -ft(f, e)^T.
            np.testing.assert_allclose(forward[0], np.swapaxes(reverse[0], 1, 2), rtol=0, atol=1e-12 * abs(forward).max())
            np.testing.assert_allclose(forward[3], np.swapaxes(reverse[3], 1, 2), rtol=0, atol=1e-12 * abs(forward).max())
            np.testing.assert_allclose(forward[1], -np.swapaxes(reverse[2], 1, 2), rtol=0, atol=1e-12 * abs(forward).max())

    def test_acute_junction_pairs_including_one_on_the_axis(self):
        k = K * complex(np.sqrt((2.5 - 0.08j) * (1 - 0.01j)))
        kinds = ('efie', 'ibc')
        for angle in (12.5, 1.0):
            half = math.radians(angle)
            length = WAVELENGTH / 40
            gp = Generatrix(np.array([(0.15 - length, 0.0), (0.15, 0.0)]))
            gq = Generatrix(np.array([(0.15, 0.0), (0.15 - length * math.cos(half), length * math.sin(half))]))
            points = sharp_pairs.junction_points(gp, 0, gq, 0, 'corner10', 0, MODES)
            self.assertEqual(sharp_pairs.junction_pair(gp, 0, gq, 0, 'corner10')[0], 'acute')
            nodes = np.array([gp.nodes[0], gp.nodes[1], gq.nodes[1]])
            reference = _blocks(gp, 0, gq, 0, sharp_pairs._cached_rule(tuple(nodes.ravel()), (1, 0), 32, 0.25, 1.0), k, kinds)
            self.assertLess(sharp_pairs.relative_change(_blocks(gp, 0, gq, 0, points, k, kinds), reference), 1e-6)
            # Two surfaces leaving one axis point: no ring scale, no runaway grading.
            top, d = np.array([0.0, 0.04]), np.array([0.5, -math.sqrt(0.75)])
            turn = np.array([[math.cos(half), -math.sin(half)], [math.sin(half), math.cos(half)]])
            gp = Generatrix(np.array([top, top + length * d]))
            gq = Generatrix(np.array([top, top + length * (turn @ d)]))
            points = sharp_pairs.junction_points(gp, 0, gq, 0, 'corner00', 0, MODES)
            self.assertLess(len(points[0]), 4000)
            nodes = np.array([gp.nodes[1], gp.nodes[0], gq.nodes[1]])
            reference = _blocks(gp, 0, gq, 0, sharp_pairs._cached_rule(tuple(nodes.ravel()), (0, 0), 32, 0.25, 1.0), k, kinds)
            self.assertLess(sharp_pairs.relative_change(_blocks(gp, 0, gq, 0, points, k, kinds), reference), 1e-6)
        # Right-angle junctions are regular (no longer junction cells: the
        # same polar rule, test_bor_touching_pairs.py).
        gq = Generatrix(np.array([(0.15, 0.0), (0.15, 0.01)]))
        gp = Generatrix(np.array([(0.14, 0.0), (0.15, 0.0)]))
        self.assertEqual(sharp_pairs.junction_pair(gp, 0, gq, 0, 'corner10')[0], 'regular')
        self.assertIsInstance(sharp_pairs.junction_points(gp, 0, gq, 0, 'corner10', 0), sharp_pairs.GradedRule)

    def test_process_task_uses_the_same_rule(self):
        gen = _needle(2.0, WAVELENGTH / 40)
        pairs = [(0, 0), (0, 1), (1, 0), (3, 3)]
        task = NearTask(gen, gen, K, MODES, KINDS, depth=4, return_families=True)
        for (e, f), (blocks, _) in zip(pairs, task.run_batch(pairs)):
            direct = _blocks(gen, e, gen, f, bor._same_surface_points(gen, e, f, KINDS, 4, MODES))
            for kind in KINDS:
                np.testing.assert_array_equal(blocks[kind], direct[kind])


class SharpPairClassificationTests(unittest.TestCase):
    def test_ordinary_bodies_have_no_sharp_pairs(self):
        sphere = Generatrix(bor.sphere_generatrix(0.1, 40))
        cap = np.column_stack((np.linspace(0, 0.1, 9), np.full(9, 0.15)))
        side = np.column_stack((np.full(25, 0.1), np.linspace(0.15, -0.15, 25)))[1:]
        bottom = np.column_stack((np.linspace(0.1, 0, 9), np.full(9, -0.15)))[1:]
        cylinder = Generatrix(np.vstack((cap, side, bottom)))
        cone30 = Generatrix(_cone(60.0, 24, 8))
        for gen in (sphere, cylinder, cone30):
            self.assertEqual([(e, f) for e in range(gen.n_elems) for f in (e - 1, e, e + 1)
                              if 0 <= f < gen.n_elems and sharp_pairs.same_surface_pair(gen, e, f)[0] != 'regular'], [])

    def test_rims_tips_and_thin_rods_are_sharp(self):
        self.assertEqual(sharp_pairs.same_surface_pair(_rim(30.0, 0.01), 2, 3)[0], 'acute')
        self.assertEqual(sharp_pairs.same_surface_pair(_rim(90.0, 0.01), 2, 3)[0], 'regular')
        tip = Generatrix(_cone(40.0, 24, 8))
        self.assertEqual(sharp_pairs.same_surface_pair(tip, 0, 0)[0], 'thin')
        rod = Generatrix(np.array([(0.0, 0.1), (0.002, 0.1), (0.002, 0.05), (0.002, 0.0), (0.0, 0.0)]))
        self.assertEqual(sharp_pairs.same_surface_pair(rod, 1, 1)[0], 'thin')
        self.assertEqual(sharp_pairs.same_surface_pair(rod, 0, 0)[0], 'regular')


class SharpPairSolveTests(unittest.TestCase):
    def _solve(self, points, refinement, angles=(0.0, 30.0, 90.0)):
        return bor.solve_bor(points, FREQUENCY_HZ, list(angles), workers=2,
                             bor_options=dict(near_refinement=refinement))

    def test_thin_rim_is_quadrature_converged_and_reported(self):
        # Fixed cells: 0.11 dB (HH, 90 degrees) between near_refinement 0 and 2
        # at 15 degrees, 0.06 dB at 5 degrees; now within 0.005 dB.
        for angle in (5.0, 1.0):
            base, fine = self._solve(_lens(angle, 20), 0), self._solve(_lens(angle, 20), 1)
            for key in ('sigma_vv', 'sigma_hh'):
                np.testing.assert_allclose(_db(base, key), _db(fine, key), atol=0.006)
            report = base['near_quadrature']['sharp_pairs']
            self.assertEqual((report['acute'], report['thin']), (2, 0))
            self.assertAlmostEqual(report['min_angle_deg'], angle, places=6)
            self.assertLess(report['self_check_max'], report['self_check_limit'])
            self.assertEqual(base['warnings'], [])

    def test_needle_is_quadrature_converged_without_reciprocity_warning(self):
        # Fixed cells at 2 degrees: 0.45 dB (VV, 30 degrees) between
        # near_refinement 0 and 1, and a reciprocity warning (2.3e-3).
        points = _cone(2.0, 30, 3)
        base, fine = self._solve(points, 0), self._solve(points, 1)
        for key in ('sigma_vv', 'sigma_hh'):
            np.testing.assert_allclose(_db(base, key), _db(fine, key), atol=0.002)
        summary = base['near_quadrature']
        self.assertLess(summary['efie_near_block_asymmetry_max'], 1e-4)
        self.assertGreater(summary['sharp_pairs']['thin'], 60)
        self.assertEqual(base['warnings'], [])

    def test_failed_self_check_warns(self):
        with patch.object(sharp_pairs, 'SELF_CHECK_LIMIT', 1e-14):
            result = self._solve(_lens(5.0, 10), 0, angles=(0.0,))
        self.assertTrue(any('junction quadrature self-check failed' in w and 'corners down to 5' in w
                            for w in result['warnings']))

    def test_sphere_has_no_sharp_pairs(self):
        result = bor.solve_bor(bor.sphere_generatrix(0.1, 24), FREQUENCY_HZ, [0.0], workers=1)
        self.assertNotIn('sharp_pairs', result['near_quadrature'])
        self.assertEqual(result['near_quadrature']['touching_pairs']['pairs'], 3 * 24 - 2)


class CornerGuardTests(unittest.TestCase):
    def test_threshold_is_the_validated_quarter_degree(self):
        bor_geometry.require_resolved_corners(_lens(0.25, 6))
        bor_geometry.require_resolved_corners(_lens(0.25 + 1e-9, 6))
        bor_geometry.require_resolved_corners(_lens(5.0, 6))
        with self.assertRaisesRegex(ValueError, 'not validated below 0.25 degrees'):
            bor_geometry.require_resolved_corners(_lens(0.2, 6))


if __name__ == '__main__':
    unittest.main()
