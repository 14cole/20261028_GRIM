"""Touching panels meeting at small angles (thin wedge tips, feathered coatings).

The touching-pair rule's angular variable could not resolve the kernel's near
singularity once the panels met at a few degrees: K' blocks were 0.24 off at
0.1 degree, independent of the mesh, so a 0.1 degree PEC wedge certified
1.7 dB off. These tests check the angle-graded rule against an independent
reference, that other pairs keep the fixed rule bit for bit, and the solves
and certificate it fixes.
"""
import contextlib
import io
import math
from pathlib import Path
import sys
import unittest
from unittest import mock

import numpy as np
from scipy.special import hankel2

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ghost_backend.twod.operators as ops
import ghost_backend.twod.polynomial_quadrature as pq
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
from ghost_backend.twod.geometry import LinearElement
from ghost_backend.twod.solver import (
    solve_monostatic_rcs_2d,
    solve_monostatic_rcs_2d_certified,
    solve_monostatic_rcs_2d_single_polarization,
)

K = 2 * math.pi / 0.3


def element(p0, p1, normal, index, nodes):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    length = float(np.linalg.norm(p1 - p0))
    return LinearElement('w', 2, 0, 0, 0, nodes, p0, p1, (p0 + p1) / 2, (p1 - p0) / length,
                         np.asarray(normal, float), length, index)


def corner_pair(angle_deg, length=0.0075, ratio=1.0):
    """Panels from a shared corner at the origin, ``angle_deg`` apart (the source runs into it)."""
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    obs = element((0, 0), (length, 0), (0, -1), 0, (0, 1))
    src = element((ratio * length * c, ratio * length * s), (0, 0), (-s, c), 1, (2, 0))
    return obs, src


def reference_blocks(obs, src, radial=60, points=30):
    """S, K, K' blocks: radial t**4 grading and a composite angular rule graded
    toward the near singularity far below the solver's (scipy kernels, no floors)."""
    t, w = np.polynomial.legendre.leggauss(radial)
    t, w = (t + 1) / 2, w / 2
    u, wu = t**4, 4 * t**3 * w
    g, gw = np.polynomial.legendre.leggauss(points)
    g, gw = (g + 1) / 2, gw / 2
    d_o, d_s = obs.p1 - obs.p0, src.p0 - src.p1
    total = np.zeros((3, 2, 2), complex)
    for first, c in enumerate(ops._touching_angular_poles(d_o, d_s)):
        a = min(max(c.real, 0.0), 1.0)
        edges = {0.0, a, 1.0}
        for side, sign in ((a, -1), (1 - a, 1)):
            step = side
            while step > 1e-3 * abs(c - a):
                step /= 2
                edges.add(a + sign * step)
        edges = np.array(sorted(edges))
        v = np.concatenate([lo + (hi - lo) * g for lo, hi in zip(edges[:-1], edges[1:])])
        wv = np.concatenate([(hi - lo) * gw for lo, hi in zip(edges[:-1], edges[1:])])
        U, V = np.repeat(u, v.size), np.tile(v, u.size)
        weight = np.outer(wu * u, wv).ravel()
        x, y = (U, U * V) if first == 0 else (U * V, U)
        d = x[:, None] * d_o - y[:, None] * d_s
        r = np.linalg.norm(d, axis=1)
        h1 = hankel2(1, K * r)
        kernels = (0.25j * hankel2(0, K * r), 0.25j * K * h1 * (d @ src.normal) / r,
                   -0.25j * K * h1 * (d @ obs.normal) / r)
        po, ps = np.stack((1 - x, x), -1), np.stack((y, 1 - y), -1)
        total += np.einsum('kq,q,qa,qb->kab', np.stack(kernels), weight, po, ps)
    return total * obs.length * src.length


def production_blocks(obs, src, batched=False):
    if batched:
        shared = np.array([[True, False]])
        s, k = ops._integrate_linear_touching_pairs_sk_batched([(obs, src)], shared, K, False, 9)
        _, kp = ops._integrate_linear_touching_pairs_sk_batched([(obs, src)], shared, K, True, 9)
        return np.stack((s[0], k[0], kp[0]))
    s, k = ops._integrate_linear_touching_duffy_sk_vectorized(obs, src, K, False, (0., 1.), (0., 1.), True, False, 9)
    _, kp = ops._integrate_linear_touching_duffy_sk_vectorized(obs, src, K, True, (0., 1.), (0., 1.), True, False, 9)
    return np.stack((s, k, kp))


def relative(a, b):
    return [float(np.linalg.norm(x - y) / np.linalg.norm(y)) for x, y in zip(a, b)]


L = 0.3


def seg(name, typ, props, pts):
    lines = [f"Segment: {name} {typ}", "properties: " + " ".join(str(p) for p in props)]
    lines += [f"{a!r} {b!r} {c!r} {d!r}" for (a, b), (c, d) in zip(pts[:-1], pts[1:])]
    return "\n".join(lines)


def snapshot(segments, dielectrics=""):
    text = ("Title: t\n" + "\n\n".join(segments) + "\n\nIBCS_Resistances:\n\nDielectrics:\n"
            + dielectrics + "\n")
    return build_geometry_snapshot(*parse_geometry(text))


def rhombus(theta_deg, n):
    """PEC rhombus of chord 0.3 m (one wavelength at 1 GHz), tip angle theta at both ends."""
    t = 0.5 * L * math.tan(math.radians(theta_deg) / 2)
    return snapshot([seg('w', 2, [2, n, 0, 0, 0], [(L / 2, 0.0), (0.0, -t), (-L / 2, 0.0), (0.0, t), (L / 2, 0.0)])])


def feathered(alpha_deg, n):
    """TYPE 3 coating (eps 4-0.4j) tapering at alpha onto a 0.4 x 0.02 m PEC plate (TYPE 4 under it)."""
    a, h = 0.1, 0.1 * math.tan(math.radians(alpha_deg))
    pec = [(a, 0.0), (0.2, 0.0), (0.2, -0.02), (-0.2, -0.02), (-0.2, 0.0), (-a, 0.0)]
    return snapshot([seg('pec', 2, [2, n, 0, 0, 0], pec),
                     seg('under', 4, [4, n, 0, 1, 0], [(-a, 0.0), (a, 0.0)]),
                     seg('coat', 3, [3, n, 0, 1, 0], [(-a, 0.0), (0.0, h), (a, 0.0)])],
                    "1 4.0 -0.4 1.0 0.0\n")


def quiet(function, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return function(*args, **kwargs)


def rcs_db(result):
    out = {}
    for sample in sorted(result['samples'], key=lambda s: s['theta_inc_deg']):
        out.setdefault(sample.get('polarization', 'TM'), []).append(10 * math.log10(sample['rcs_linear']))
    return out


class AcuteTouchingBlocks(unittest.TestCase):
    def test_blocks_match_reference_down_to_hundredth_degree(self):
        for ratio in (1.0, 0.5, 3.0):
            for angle in (10.0, 1.0, 0.1, 0.01):
                obs, src = corner_pair(angle, ratio=ratio)
                self.assertTrue(ops._touching_is_acute(obs.p1 - obs.p0, src.p0 - src.p1))
                reference = reference_blocks(obs, src)
                for batched in (False, True):
                    errors = relative(production_blocks(obs, src, batched), reference)
                    self.assertLess(max(errors), 2e-13, (ratio, angle, batched, errors))

    def test_fixed_rule_was_wrong_and_is_mesh_independent(self):
        # The former rule's error depends on the angle alone, so it survives refinement.
        obs, src = corner_pair(0.1)
        with mock.patch.object(ops, '_ACUTE_TOUCHING_RHO', 0.0):
            for length in (0.0075, 0.00075):
                obs, src = corner_pair(0.1, length)
                errors = relative(production_blocks(obs, src), reference_blocks(obs, src))
                self.assertGreater(errors[2], 0.1)

    def test_other_pairs_keep_the_fixed_rule_bit_for_bit(self):
        for angle, ratio in ((170.0, 1.0), (90.0, 1.0), (30.0, 1.0), (90.0, 0.5)):
            obs, src = corner_pair(angle, ratio=ratio)
            self.assertFalse(ops._touching_is_acute(obs.p1 - obs.p0, src.p0 - src.p1))
            with mock.patch.object(ops, '_acute_touching_rule', side_effect=AssertionError):
                current = production_blocks(obs, src)
                batched = production_blocks(obs, src, batched=True)
            with mock.patch.object(ops, '_ACUTE_TOUCHING_RHO', 0.0):  # the former selection
                np.testing.assert_array_equal(production_blocks(obs, src), current)
                np.testing.assert_array_equal(production_blocks(obs, src, batched=True), batched)

    def test_polynomial_shared_blocks_use_the_graded_rule(self):
        obs, src = corner_pair(0.1)
        quad = [element(e.p0, e.p1, e.normal, e.panel_index, e.node_ids + (9 + e.panel_index,)) for e in (obs, src)]
        reference = reference_blocks(obs, src)
        # Linear hats in the quadratic Lagrange basis (ends, then midpoint): 1 - x = L0 + L_mid / 2.
        project = np.array([[1, 0, .5], [0, 1, .5]])
        for s_block, k_block in (pq.block(*quad, K, True, 20), pq.near_blocks([tuple(quad)], K, True)[0]):
            errors = relative([project @ s_block @ project.T, project @ k_block @ project.T],
                              [reference[0], reference[2]])
            self.assertLess(max(errors), 1e-11, errors)


class TouchingFloors(unittest.TestCase):
    def test_fixed_rule_blocks_match_the_reference_without_floors(self):
        # The former 1e-12 m distance mask and k r floor cost 1e-9 of a K block
        # for millimetre panels and 1e-6 for micrometre ones (S 4e-14, acute S 7e-12).
        for length in (0.0075, 1e-4, 1e-6):
            for angle, ratio in ((170.0, 1.0), (90.0, 0.5), (30.0, 1.0), (10.0, 1.0)):
                obs, src = corner_pair(angle, length, ratio)
                reference = reference_blocks(obs, src)
                for batched in (False, True):
                    errors = relative(production_blocks(obs, src, batched), reference)
                    self.assertLess(max(errors), 5e-14, (length, angle, ratio, batched, errors))

    def test_folded_zero_angle_pair_drops_coincident_samples(self):
        # Panels folding back at zero angle put rule nodes exactly on their
        # singular line (r = 0). Those samples carry no weight: the collinear K
        # and K' vanish (they were NaN with the 0/0 projection) and S is finite.
        seen = []
        values = ops._near_kernel_values

        def spy(k0, distance, *args, **kwargs):
            seen.append(int(np.sum(distance == 0)))
            return values(k0, distance, *args, **kwargs)
        for ratio in (0.5, 1.0, 3.0):
            obs, src = corner_pair(0.0, ratio=ratio)
            for batched in (False, True):
                with mock.patch.object(ops, '_near_kernel_values', side_effect=spy):
                    s, k, kp = production_blocks(obs, src, batched)
                self.assertTrue(np.all(np.isfinite(s)) and np.any(s != 0))
                np.testing.assert_array_equal(k, 0.)
                np.testing.assert_array_equal(kp, 0.)
        self.assertGreater(sum(seen), 0)


class AcuteCornerSolves(unittest.TestCase):
    def test_thin_wedge_converges_to_the_strip(self):
        strip = rcs_db(quiet(solve_monostatic_rcs_2d_single_polarization,
                             snapshot([seg('s', 2, [2, 320, 0, 0, 0], [(L / 2, 0.0), (-L / 2, 0.0)])]),
                             [1.0], [0.0, 30.0], 'TM', geometry_units='meters'))['TM']
        coarse, fine = (rcs_db(quiet(solve_monostatic_rcs_2d, rhombus(0.3, n), [1.0], [0.0, 30.0],
                                     geometry_units='meters'))['HH'] for n in (10, 20))
        # Before the fix: N=10 and 20 differed by 0.01..0.06 dB and lay 0.6 dB from the strip.
        self.assertLess(max(abs(a - b) for a, b in zip(coarse, fine)), 0.02)
        self.assertLess(max(abs(a - b) for a, b in zip(fine, strip)), 0.03)

    def test_feathered_coating_converges(self):
        coarse, fine = (rcs_db(quiet(solve_monostatic_rcs_2d, feathered(0.3, n), [1.0], [0.0, 90.0],
                                     geometry_units='meters')) for n in (-10, -20))
        # 160 panels per wavelength (after the fix): VV -23.210 / 5.884, HH -11.566 / 5.410 dB.
        # Before, VV moved 0.42 dB between these meshes and published -23.41 at -20.
        for pol, refined in (('VV', (-23.210, 5.884)), ('HH', (-11.566, 5.410))):
            self.assertLess(max(abs(a - b) for a, b in zip(coarse[pol], fine[pol])), 0.1, pol)
            self.assertLess(max(abs(a - b) for a, b in zip(fine[pol], refined)), 0.06, pol)

    def test_certificate_matches_the_refined_wedge(self):
        result = quiet(solve_monostatic_rcs_2d_certified, rhombus(0.3, 0), [1.0], [0.0, 30.0],
                       geometry_units='meters')
        published = rcs_db(result)['HH']
        # N=160 per primitive (after the fix): -13.2248 / -12.6318 dB. Before, the
        # certificate published -13.859 / -13.142 with no warning.
        for got, want in zip(published, (-13.2248, -12.6318)):
            self.assertLess(abs(got - want), 0.05)
        self.assertTrue(result['metadata']['mesh_convergence_certified'])
        self.assertTrue(any('acute corners' in note for note in result['metadata']['information']))


class AcuteCornerReport(unittest.TestCase):
    def test_report_and_failing_self_check_warn(self):
        from ghost_backend.twod.solver import _note_acute_corners
        obs, src = corner_pair(0.1)
        mesh = mock.Mock(elements=[obs, src])
        report = ops.acute_touching_report(mesh, K)
        self.assertEqual(report['pairs'], 1)
        self.assertAlmostEqual(report['min_angle_deg'], 0.1, places=9)
        self.assertLess(report['self_check'], 1e-12)
        right = corner_pair(90.0)
        self.assertIsNone(ops.acute_touching_report(mock.Mock(elements=list(right)), K))
        notices = mock.Mock()
        with mock.patch.object(ops, 'ACUTE_SELF_CHECK_LIMIT', 0.0):
            _note_acute_corners(mesh, K, notices, None)
        notices.inform_once.assert_called_once()
        notices.warn_once.assert_called_once()
        self.assertIn('self-check failed', notices.warn_once.call_args[0][0])


if __name__ == '__main__':
    unittest.main()
