"""Every touching BoR element pair uses the graded polar rule (October 2026).

Self, adjacent and junction pairs of ordinary bodies used fixed graded cells
whose block error did not shrink with the mesh (2e-3 of a sphere's self
block, 0.2 of its pole element's, 3e-5..4e-4 of a junction's rotated-PV
block). They now use bor.sharp_pairs like the sharp pairs, with a sampled
self-check on every solve; the far fields then converge to the exact series
at the facet rate.
"""
from pathlib import Path
import math
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.bor import solver as bor, sharp_pairs
from ghost_backend.bor.kernels import Generatrix
from ghost_backend.bor.near_parallel import NearTask
from ghost_backend.validation import sphere as mie

WAVELENGTH = 0.3
K = 2.0 * math.pi / WAVELENGTH
KINDS = ('efie', 'mfie', 'ibc')


def _sphere(radius, count):
    return Generatrix(bor.sphere_generatrix(radius, count))


def _corner(angle_degrees, length, radius=0.15):
    """Three elements on each side of a corner at (radius, 0) of included angle ``angle_degrees``."""
    half = math.radians(angle_degrees) / 2
    up = [(radius - j * length * math.cos(half), j * length * math.sin(half)) for j in (3, 2, 1)]
    down = [(radius - j * length * math.cos(half), -j * length * math.sin(half)) for j in (1, 2, 3)]
    return Generatrix(np.array(up + [(radius, 0.0)] + down))


def _cone_tip(half_degrees, length, count=5):
    half = math.radians(half_degrees)
    return Generatrix(np.array([(j * length * math.sin(half), -j * length * math.cos(half))
                                for j in range(count + 1)]))


def _junction(radius, arrive, leave, length):
    """A pair of one-element surfaces meeting at (radius, 0): p arrives along ``arrive``, q leaves along ``leave``."""
    corner = np.array([radius, 0.0])
    arrive, leave = (np.asarray(v, float) / np.hypot(*v) for v in (arrive, leave))
    return Generatrix(np.array([corner - length * arrive, corner])), Generatrix(np.array([corner, corner + length * leave]))


def _blocks(gp, e, gq, f, points, k=K, modes=8, kinds=KINDS):
    return bor._contract_near_points(gp, e, gq, f, k, modes, kinds, points, signed=False)


def _reference(points, ends, modes):
    """The graded rule with 32 points per piece and every graded stop 4x deeper."""
    return sharp_pairs._cached_rule(tuple(np.asarray(points, float).ravel()), ends, 32, 0.25,
                                    sharp_pairs._ring_factor(modes))


def _same_surface_error(gen, e, f, k=K, modes=8, kinds=KINDS):
    _, points, ends = sharp_pairs._same_surface_geometry(gen, e, f)
    production = _blocks(gen, e, gen, f, bor._same_surface_points(gen, e, f, kinds, 4, modes), k, modes, kinds)
    return sharp_pairs.relative_change(production, _blocks(gen, e, gen, f, _reference(points, ends, modes), k, modes, kinds))


class TouchingPairAccuracyTests(unittest.TestCase):
    def test_smooth_axis_and_corner_pairs_meet_the_reference(self):
        # Fixed cells on these pairs: sphere pole self 0.2 (EFIE), equator
        # self 2e-3, 90 degree corner MFIE 2.7e-3, cone tip self 0.7.
        sphere = _sphere(3.0 / K, 24)
        cases = [(sphere, pair) for pair in ((0, 0), (0, 1), (1, 1), (12, 12), (12, 13))]
        cases += [(_corner(angle, WAVELENGTH / 10), pair) for angle in (90.0, 150.0) for pair in ((2, 3), (2, 2))]
        cases += [(_cone_tip(half, WAVELENGTH / 10), pair) for half in (30.0, 90.0) for pair in ((0, 0), (0, 1), (2, 2))]
        for gen, (e, f) in cases:
            with self.subTest(nodes=gen.n_nodes, pair=(e, f)):
                self.assertLess(_same_surface_error(gen, e, f), 1e-7)
        cells = _blocks(sphere, 12, sphere, 12, bor._cell_points('diag', depth=4))
        _, points, ends = sharp_pairs._same_surface_geometry(sphere, 12, 12)
        self.assertGreater(sharp_pairs.relative_change(cells, _blocks(sphere, 12, sphere, 12, _reference(points, ends, 8))), 1e-3)

    def test_high_modes_and_material_wavenumbers(self):
        sphere = _sphere(3.0 / K, 24)
        tip = _cone_tip(30.0, WAVELENGTH / 10)
        for modes in (30, 60):
            for gen, pair in ((sphere, (1, 1)), (tip, (0, 0)), (tip, (0, 1))):
                with self.subTest(modes=modes, pair=pair):
                    self.assertLess(_same_surface_error(gen, *pair, modes=modes), 1e-7)
        # Lossy dielectric interiors: 3.2 elements per medium wavelength.
        k = K * complex(np.sqrt(10 - 1j))
        for gen, pair in ((sphere, (12, 12)), (_corner(90.0, WAVELENGTH / 10), (2, 3)), (tip, (0, 0))):
            with self.subTest(pair=pair, k=k):
                self.assertLess(_same_surface_error(gen, *pair, k=k), 1e-7)

    def test_junction_pairs_meet_the_reference(self):
        # Junction cells (order 10, depth 7, 2420 points): rotated-PV blocks
        # 3e-5..4e-4 off at 45..150 degrees, EFIE 1e-6 at a thin junction.
        kinds = ('efie', 'ibc')
        length = WAVELENGTH / 10
        cases = []
        for angle in (180.0, 135.0, 90.0, 45.0):
            h = math.radians(angle)
            cases.append(_junction(0.15, (0, -1), (math.sin(h), math.cos(h)), length))
        cases.append(_junction(0.3 * length, (0.05, -1), (0.05, -1), length))
        for k in (K, K * complex(np.sqrt((3 - 0.1j) * (1 - 0.02j)))):
            for modes in (8, 30):
                for gp, gq in cases:
                    with self.subTest(k=k, modes=modes, nodes=gq.nodes.tolist()):
                        points, ends = sharp_pairs._junction_geometry(gp, 0, gq, 0, 'corner10')
                        production = _blocks(gp, 0, gq, 0, bor._junction_points(gp, 0, gq, 0, 'corner10', 0, modes),
                                             k, modes, kinds)
                        reference = _blocks(gp, 0, gq, 0, _reference(points, ends, modes), k, modes, kinds)
                        self.assertLess(sharp_pairs.relative_change(production, reference), 1e-7)

    def test_rule_is_reciprocal_on_ordinary_pairs(self):
        sphere = _sphere(0.1, 20)
        for e in (0, 7):
            forward = _blocks(sphere, e, sphere, e + 1, bor._same_surface_points(sphere, e, e + 1, KINDS, 4))['efie']
            reverse = _blocks(sphere, e + 1, sphere, e, bor._same_surface_points(sphere, e + 1, e, KINDS, 4))['efie']
            atol = 1e-12 * abs(forward).max()
            np.testing.assert_allclose(forward[0], np.swapaxes(reverse[0], 1, 2), rtol=0, atol=atol)
            np.testing.assert_allclose(forward[3], np.swapaxes(reverse[3], 1, 2), rtol=0, atol=atol)
            np.testing.assert_allclose(forward[1], -np.swapaxes(reverse[2], 1, 2), rtol=0, atol=atol)


class TouchingPairClassificationTests(unittest.TestCase):
    def test_junction_elements_are_classified_geometrically(self):
        length = WAVELENGTH / 40
        gp, gq = _junction(0.15, (0, -1), (1, 0), length)
        self.assertEqual(sharp_pairs.junction_pair(gp, 0, gq, 0, 'corner10')[0], 'regular')
        gp, gq = _junction(0.15, (0, -1), (math.sin(math.radians(30)), math.cos(math.radians(30))), length)
        self.assertEqual(sharp_pairs.junction_pair(gp, 0, gq, 0, 'corner10')[0], 'acute')
        # A straight-through junction of steep elements near the axis (the
        # edge of a coating on a needle) is thin, whatever its angle.
        gp, gq = _junction(0.3 * length, (0.05, -1), (0.05, -1), length)
        kind, angle, ring = sharp_pairs.junction_pair(gp, 0, gq, 0, 'corner10')
        self.assertEqual(kind, 'thin')
        self.assertAlmostEqual(angle, 180.0, places=6)
        self.assertLess(ring, sharp_pairs.THIN_RING_RATIO)

    def test_probes_include_the_most_severe_pair_of_each_class(self):
        records = [('regular', 90.0, 30.0), ('regular', None, 2.0), ('thin', None, 3.0), ('thin', None, 0.5),
                   ('acute', 20.0, 9.0), ('acute', 5.0, 9.0), ('regular', 170.0, 12.0)]
        self.assertEqual(sharp_pairs.check_probes(records, 4), {0, 1, 2, 3, 4, 5})
        # 56 records: every 4th sharp pair, every 16th regular one, the most severe of each class.
        self.assertEqual(sharp_pairs.check_probes(records * 8, 4), {0, 1, 2, 3, 4, 5, 16, 18, 30, 32, 36, 44, 46})
        self.assertEqual(sharp_pairs.check_probes(records, 0), set(range(len(records))))


class TouchingPairSolveTests(unittest.TestCase):
    def test_failed_quadrature_cannot_be_mesh_certified(self):
        from unittest.mock import patch
        from ghost_backend.bor import dispatch
        from test_bor_physics_regression import _pec_sphere_snapshot
        with patch.object(sharp_pairs, 'relative_change', return_value=1e-2):
            with self.assertRaisesRegex(RuntimeError, 'base quadrature self-check failed'):
                dispatch.solve_monostatic_rcs_bor_certified(
                    _pec_sphere_snapshot(explicit_elements=-40), [1.], [0.],
                    geometry_units='meters', workers=1)

    def test_material_and_conductor_reports_gate_both_meshes(self):
        from ghost_backend.bor.dispatch import _require_touching_quadrature
        for phase in ('base', 'fine'):
            for error in (1e-2, float('nan'), float('inf')):
                report = dict(self_check_max=error, self_check_limit=1e-5, self_checked_pairs=4)
                for fields in ({'touching_pair_quadrature': report},
                               {'near_quadrature': {'touching_pairs': report}}):
                    result = {'metadata': {'per_frequency': [dict(frequency_ghz=1., **fields)]}}
                    with self.assertRaisesRegex(RuntimeError, phase + ' quadrature'):
                        _require_touching_quadrature(result, phase)

    def test_nonfinite_and_zero_reference_checks_fail_closed(self):
        zero = {'efie': np.zeros(2, complex)}
        bad = {'efie': np.array([float('nan'), 1.], complex)}
        self.assertTrue(np.isinf(sharp_pairs.relative_change(zero, bad)))
        self.assertTrue(np.isinf(sharp_pairs.relative_change(bad, zero)))
        self.assertTrue(np.isinf(sharp_pairs.relative_change({'efie': np.ones(2)}, zero)))
        self.assertEqual(sharp_pairs.relative_change(zero, zero), 0.)

    def test_self_check_covers_ordinary_bodies(self):
        cap = np.column_stack((np.linspace(0, 0.1, 9), np.full(9, 0.15)))
        side = np.column_stack((np.full(25, 0.1), np.linspace(0.15, -0.15, 25)))[1:]
        bottom = np.column_stack((np.linspace(0.1, 0, 9), np.full(9, -0.15)))[1:]
        result = bor.solve_bor(np.vstack((cap, side, bottom)), 1e9, [0.0, 60.0], workers=2)
        summary = result['near_quadrature']
        touching = summary['touching_pairs']
        self.assertEqual(touching['pairs'], 3 * 40 - 2)
        self.assertGreaterEqual(touching['self_checked_pairs'], touching['pairs'] // 16)
        self.assertLess(touching['self_check_max'], 1e-7)
        self.assertNotIn('sharp_pairs', summary)
        self.assertEqual(summary['self_and_junction_rule'], 'graded_polar_singular_point')
        # Self pairs are symmetric and adjacent pairs reciprocal by construction.
        self.assertLess(summary['efie_near_block_asymmetry_max'], 1e-12)
        self.assertEqual(result['warnings'], [])

    def test_junction_self_check_is_reported(self):
        # A lid from the axis ending on a node of a sphere: one junction point.
        core = bor.BorPecSolver(bor.sphere_generatrix(0.04, 12), 3e9)
        edge = core.gen.nodes[1]
        lid = bor.BorPecSolver(np.linspace((0.0, 0.05), edge, 5), 3e9)
        cross = bor.BorCrossOperators(lid, core)
        junctions = [pair for pair, kind in cross.pair_kind.items() if kind is not None]
        self.assertTrue(junctions)
        cross.prepare(6)
        summary = bor._touching_pair_summary((cross,))
        self.assertEqual(summary['pairs'], len(junctions))
        self.assertGreater(summary['self_checked_pairs'], 0)
        self.assertLess(summary['self_check_max'], 1e-7)

    def test_process_task_returns_the_in_process_blocks_and_check(self):
        gen = _sphere(0.1, 16)
        pairs = [(0, 0), (0, 1), (1, 0), (5, 5), (5, 7)]
        checked = frozenset({(0, 0), (1, 0)})
        task = NearTask(gen, gen, K, 6, KINDS, depth=4, return_families=True, check_pairs=checked)
        for (e, f), (blocks, refinement) in zip(pairs, task.run_batch(pairs)):
            if abs(e - f) > 1:
                self.assertIsInstance(refinement, tuple)
                continue
            check = sharp_pairs.pair_points(gen, e, f, 4, 6, check=True) if (e, f) in checked else None
            direct, change = bor._touching_blocks(gen, e, gen, f, bor._same_surface_points(gen, e, f, KINDS, 4, 6),
                                                  check, K, 6, KINDS)
            self.assertEqual(refinement, change)
            self.assertEqual(refinement is None, (e, f) not in checked)
            for kind in KINDS:
                np.testing.assert_array_equal(blocks[kind], direct[kind])

    def test_deeply_graded_needle_tip_keeps_full_rank(self):
        # The rank loss seen with five or more tip grading levels came from
        # inner tip nodes snapped onto the axis (an element on the axis), not
        # from the integration: kept off the axis, eight levels (innermost
        # radius 2e-8 wavelengths) solve and agree with four.
        def needle(levels, count=24, angle=2.0):
            radius = 0.3 * math.tan(math.radians(angle) / 2)
            breaks = np.r_[0.0, 2.0 ** -np.arange(levels, 0, -1) / count, np.arange(1, count + 1) / count]
            side = np.column_stack((radius * breaks, 0.15 - 0.3 * breaks))
            base = np.column_stack((np.linspace(radius, 0.0, 4), np.full(4, -0.15)))[1:]
            return np.vstack((side, base))
        results = [bor.solve_bor(needle(levels), 1e9, [0.0, 30.0, 90.0], workers=2) for levels in (4, 8)]
        for result in results:
            self.assertEqual(result['warnings'], [])
        for key in ('sigma_vv', 'sigma_hh'):
            np.testing.assert_allclose(10 * np.log10(results[1][key]), 10 * np.log10(results[0][key]), atol=0.01)
        pinched = needle(4)
        pinched[1, 0] = 0.0
        with self.assertRaisesRegex(ValueError, 'node 1 .* lies on the rotation axis'):
            bor.solve_bor(pinched, 1e9, [0.0], workers=1)

    def test_pec_sphere_converges_to_the_exact_series_at_the_facet_rate(self):
        # With the fixed cells the error ratio between 24 and 48 elements was
        # 4.9 and the Richardson limit 2.0e-3 dB off the exact series (their
        # error partly offset the facet error); now 4.0 and 3e-5 dB.
        frequency = 1e9
        radius = 3.0 / (2 * math.pi * frequency / mie.C0)
        exact = 10 * math.log10(mie.sigma_pec_sphere(radius, frequency))
        errors = [10 * math.log10(bor.solve_bor(bor.sphere_generatrix(radius, n), frequency, [0.0], workers=2)['sigma_vv'][0]) - exact
                  for n in (24, 48)]
        self.assertAlmostEqual(errors[0] / errors[1], 4.0, delta=0.1)
        self.assertLess(abs((4 * errors[1] - errors[0]) / 3), 2e-4)


if __name__ == '__main__':
    unittest.main()
