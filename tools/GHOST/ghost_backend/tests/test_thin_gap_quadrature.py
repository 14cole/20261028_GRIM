"""Thin-gap near quadrature: the level-batched box recursion and the semi-analytic thin-gap moments.

The batched recursion must reproduce the per-pair recursion bit for bit; the
thin-gap moments must agree with it (and with the polynomial per-task rule) to
the adaptive target, and stay converged where the gap is far below a panel.
"""
from pathlib import Path
import io
import contextlib
import dataclasses
import sys
import threading
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ghost_backend.twod.operators as ops
import ghost_backend.twod.polynomial_quadrature as pq
from ghost_backend.twod.assembly import thin_gap
from ghost_backend.twod.assembly.native import near as native_near
from ghost_backend.twod.basis import coefficients
from ghost_backend.twod.geometry import LinearElement

K_VALUES = (2 * np.pi / .3, 2 * np.pi / .3 * 2 * (1 - .05j))


def element(p0, p1, index, flip=False, degree=1):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    length = float(np.linalg.norm(p1 - p0))
    tangent = (p1 - p0) / length
    normal = np.array([tangent[1], -tangent[0]]) * (-1. if flip else 1.)
    return LinearElement(name='panel', seg_type=2, ibc_flag=0, pos_mat=0, neg_mat=0,
                         node_ids=tuple(range(10 * index, 10 * index + degree + 1)), p0=p0, p1=p1,
                         center=.5 * (p0 + p1), tangent=tangent, normal=normal, length=length,
                         panel_index=index)


def close_pairs(gaps, seed, degree=1, count=3):
    """Nearly parallel (and some oblique) separated pairs at gap/length ``gaps``."""
    rng = np.random.default_rng(seed)
    pairs = []
    for gap in gaps:
        for trial in range(count):
            length = .03 * rng.uniform(.5, 2.)
            angle = rng.uniform(-.03, .03) if trial < 2 else rng.uniform(-.4, .4)
            start = np.array([length * rng.uniform(-.5, .5), gap * length * (1 if trial % 2 else -1)])
            end = start + length * rng.uniform(.7, 1.4) * np.array([np.cos(angle), np.sin(angle)])
            obs = element((0., 0.), (length, 0.), 0, degree=degree)
            src = element(start, end, 1, flip=bool(trial % 2), degree=degree)
            pairs.append((obs, src) if trial != 1 else (src, obs))
    return pairs


def relative(a, b):
    return float(np.linalg.norm(np.asarray(a) - np.asarray(b)) / np.linalg.norm(np.asarray(b)))


class BatchedRecursionTests(unittest.TestCase):
    def test_level_batched_recursion_is_the_per_pair_recursion(self):
        pairs = close_pairs((.3, .1, .03), seed=2, count=2) + close_pairs((.5, .3), seed=12)
        for k in K_VALUES:
            for derivative in (False, True):
                for want in ((True, True), (True, False), (False, True)):
                    s, kb = ops._integrate_linear_pairs_adaptive_sk_batched(
                        [o for o, _ in pairs], [s for _, s in pairs], k, derivative, 16, *want)
                    for i, (obs, src) in enumerate(pairs):
                        rs, rk = ops._integrate_linear_pair_adaptive_sk(obs, src, k, derivative, 16, 16, *want)
                        self.assertEqual(s[i].tobytes(), rs.tobytes(), (k, derivative, want, i))
                        self.assertEqual(kb[i].tobytes(), rk.tobytes(), (k, derivative, want, i))

    def test_batched_recursion_reports_the_depth_limit(self):
        obs, src = close_pairs((.001,), seed=3, count=1)[0]
        with self.assertRaises(FloatingPointError):
            ops._integrate_linear_pairs_adaptive_sk_batched([obs], [src], K_VALUES[0], False, 16, max_depth=2)


class ThinGapLinearTests(unittest.TestCase):
    def test_qualification(self):
        obs = element((0., 0.), (1., 0.), 0)
        for gap, expected in ((.04, True), (.06, False)):
            src = element((.1, gap), (1.1, gap), 1)
            self.assertEqual(bool(ops._thin_gap_mask([obs], [src])[0]), expected)
        # A short panel far along the longer panel's line does not qualify.
        self.assertFalse(ops._thin_gap_mask([obs], [element((2.5, .01), (3.5, .01), 1)])[0])

    def test_agrees_with_the_box_recursion(self):
        pairs = [p for p in close_pairs((.04, .01, .003), seed=4)
                 if ops._thin_gap_mask([p[0]], [p[1]])[0]]
        self.assertGreater(len(pairs), 5)
        for k in K_VALUES:
            for derivative in (False, True):
                s, kb = ops._thin_gap_linear_blocks([o for o, _ in pairs], [s for _, s in pairs], k, derivative)
                for i, (obs, src) in enumerate(pairs):
                    rs, rk = ops._integrate_linear_pair_adaptive_sk(obs, src, k, derivative, 16, 16)
                    self.assertLess(relative(s[i], rs), 1e-9)
                    self.assertLess(relative(kb[i], rk), 1e-9)

    def test_converged_far_below_the_panel_length(self):
        pairs = [p for p in close_pairs((1e-4, 1e-6), seed=5, count=6) if ops._thin_gap_mask([p[0]], [p[1]])[0]]
        self.assertGreater(len(pairs), 3)
        arrays = [tuple(np.array([getattr(e, n) for e in side]) for n in ('p0', 'p1', 'normal'))
                  for side in zip(*pairs)]
        for k in K_VALUES:
            for derivative in (False, True):
                got = thin_gap.thin_gap_moments(*arrays, k, derivative, degree=1)
                with mock.patch.object(thin_gap, 'INNER_ORDER', 32), \
                        mock.patch.object(thin_gap, 'OUTER_ORDER', 24):
                    tight = thin_gap.thin_gap_moments(*arrays, k, derivative, degree=1, rtol=1e-13, max_depth=40)
                for a, b in zip(got, tight):
                    self.assertLess(relative(a[0], b[0]), 1e-10)
                    self.assertLess(relative(a[1], b[1]), 1e-10)

    def test_per_pair_entry_points_and_batches_agree(self):
        pairs = [p for p in close_pairs((.02, .005), seed=6) if ops._thin_gap_mask([p[0]], [p[1]])[0]]
        k = K_VALUES[0]
        s, kb = ops._thin_gap_linear_blocks([o for o, _ in pairs], [s for _, s in pairs], k, True)
        for i, (obs, src) in enumerate(pairs):
            one = ops._sk_blocks_near_linear(obs, src, k, True)
            self.assertEqual(one[0].tobytes(), s[i].tobytes())
            self.assertEqual(one[1].tobytes(), kb[i].tobytes())
        # The S-only entry point tests S alone (as the batch does without K).
        s_only, _ = ops._thin_gap_linear_blocks([o for o, _ in pairs], [s for _, s in pairs], k, False,
                                                compute_double_layer=False)
        for i, (obs, src) in enumerate(pairs):
            self.assertEqual(ops._single_layer_block_linear(obs, src, k).tobytes(), s_only[i].tobytes())


class ThinGapPolynomialTests(unittest.TestCase):
    def test_polynomial_moments_agree_with_the_per_task_rule(self):
        for degree in (2, 3):
            pairs = [p for p in close_pairs((.04, .01), seed=7 + degree, degree=degree)
                     if pq._thin_gap_mask(pq._PairGeometry([p]), [p])[0]]
            self.assertGreater(len(pairs), 3)
            for k in K_VALUES:
                for derivative in (False, True):
                    got = pq.near_blocks(pairs, k, derivative, threads=2)
                    with mock.patch.object(thin_gap, 'THIN_GAP', 0.):
                        reference = pq.near_blocks(pairs, k, derivative, threads=2)
                    for (gs, gk), (rs, rk) in zip(got, reference):
                        scale = max(np.max(np.abs(rs)), np.max(np.abs(rk)))
                        self.assertLess(np.max(np.abs(gs - rs)), 1e-8 * scale)
                        self.assertLess(np.max(np.abs(gk - rk)), 1e-8 * scale)
                    for (obs, src), (gs, gk) in zip(pairs, got):
                        one = pq.near_block(obs, src, k, derivative)
                        self.assertEqual(one[0].tobytes(), gs.tobytes())
                        self.assertEqual(one[1].tobytes(), gk.tobytes())

    def test_moments_are_cached_for_the_cubic_candidate(self):
        pairs = [p for p in close_pairs((.01,), seed=11, degree=2)
                 if pq._thin_gap_mask(pq._PairGeometry([p]), [p])[0]]
        cubic = [tuple(dataclasses.replace(e, node_ids=tuple(range(10 * e.panel_index, 10 * e.panel_index + 4)))
                       for e in pair) for pair in pairs]
        with pq.moment_cache_scope() as cache:
            pq.near_blocks(pairs, K_VALUES[1], True, threads=1)
            stored = cache.stores
            with mock.patch.object(thin_gap, 'thin_gap_moments', side_effect=AssertionError):
                pq.near_blocks(cubic, K_VALUES[1], True, threads=1)
        self.assertEqual(stored, len(pairs))


class MomentCacheThreadTests(unittest.TestCase):
    def test_concurrent_evictions(self):
        cache = pq.MomentCache(budget_bytes=4 * pq.MomentCache.ENTRY_BYTES)
        errors = []

        def store(offset):
            try:
                for i in range(2000):
                    cache.put((offset, i), i)
                    cache.get((offset, i - 1))
            except Exception as exc:  # pragma: no cover - the failure being tested
                errors.append(exc)
        threads = [threading.Thread(target=store, args=(n,)) for n in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertLessEqual(len(cache.values), 4)


@unittest.skipUnless(native_near.available(), 'native near library unavailable')
class NativeNearTests(unittest.TestCase):
    """assembly.native.near repeats the NumPy arithmetic bit for bit, at any thread count."""

    @staticmethod
    def both(function):
        try:
            native = function()
            with mock.patch.object(native_near, 'ENABLED', False):
                python = function()
        finally:
            native_near.ENABLED = True
        return native, python

    def assertBitwise(self, native, python, message=None):
        for a, b in zip(native, python):
            self.assertEqual(np.asarray(a).tobytes(), np.asarray(b).tobytes(), message)

    def test_boxes_are_the_numpy_boxes(self):
        rng = np.random.default_rng(21)
        for trial in range(24):
            n, m = 9, 40
            p0 = rng.standard_normal((n, 2))
            seg = rng.standard_normal((n, 2)) * 10 ** rng.uniform(-4, 0, (n, 1))
            q0 = p0 + rng.standard_normal((n, 2)) * 10 ** rng.uniform(-6, 0, (n, 1))
            qseg = rng.standard_normal((n, 2)) * 10 ** rng.uniform(-4, 0, (n, 1))
            if trial % 3 == 1:  # collinear: every projection is zero
                p0[:, 1] = seg[:, 1] = q0[:, 1] = qseg[:, 1] = 0.
            if trial % 3 == 2:  # coincident panels: samples on the distance floors
                q0, qseg = p0.copy(), seg.copy()
            normal = rng.standard_normal((n, 2))
            normal /= np.linalg.norm(normal, axis=1)[:, None]
            geometry = (p0, seg, np.linalg.norm(seg, axis=1), q0, qseg, np.linalg.norm(qseg, axis=1), normal)
            pair = rng.integers(0, n, m)
            intervals = np.column_stack([np.sort(rng.uniform(0, 1, (m, 2)), axis=1) for _ in range(2)])
            intervals[::7, 1] = intervals[::7, 0]  # empty boxes
            k = (K_VALUES + (0.3, 1e-3 * (1 - .1j)))[trial % 4]
            for derivative in (False, True):
                for want in ((True, True), (True, False), (False, True)):
                    self.assertBitwise(*self.both(lambda: ops._integrate_linear_boxes_sk(
                        geometry, pair, intervals, k, derivative, 3 + trial % 17, *want)), (trial, derivative, want))

    def test_thin_gap_moments_are_the_numpy_moments(self):
        pairs = [p for p in close_pairs((.04, .003, 1e-4), seed=22)
                 if ops._thin_gap_mask([p[0]], [p[1]])[0]]
        self.assertGreater(len(pairs), 5)
        arrays = [tuple(np.array([getattr(e, n) for e in side]) for n in ('p0', 'p1', 'normal'))
                  for side in zip(*pairs)]
        for k in K_VALUES:
            for table in (True, False):
                for degree in (1, 2, 3):
                    for derivative in (False, True):
                        for want in ((True, True), (True, False), (False, True)):
                            with mock.patch.object(pq, '_table_for_ends', pq._table_for_ends if table
                                                   else (lambda *args: None)):
                                self.assertBitwise(*self.both(lambda: [thin_gap.thin_gap_moments(
                                    *arrays, k, derivative, *want, degree=degree)]),
                                    (k, table, degree, derivative, want))

    def test_native_results_do_not_depend_on_the_thread_count(self):
        pairs = close_pairs((.3, .03), seed=23, count=2)
        thin = [p for p in close_pairs((.01, .001), seed=24) if ops._thin_gap_mask([p[0]], [p[1]])[0]]
        results = []
        for threads in (1, 4):
            with mock.patch.object(ops, '_ADAPTIVE_BOX_SAMPLES', 4096), \
                    mock.patch.object(thin_gap, 'BATCH_SAMPLES', 2048):
                ops.set_assembly_threads(threads)
                try:
                    results.append([ops._integrate_linear_pairs_adaptive_sk_batched(
                        [o for o, _ in pairs], [s for _, s in pairs], K_VALUES[1], True, 16),
                        ops._thin_gap_linear_blocks([o for o, _ in thin], [s for _, s in thin], K_VALUES[0], False)])
                finally:
                    ops.set_assembly_threads(1)
        for (a, b), (c, d) in zip(*results):
            self.assertBitwise((a, b), (c, d))


class ThinPlatesSolveTests(unittest.TestCase):
    def test_plates_agree_with_the_box_recursion(self):
        from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
        from ghost_backend.twod.solver import solve_monostatic_rcs_2d
        gap, width, height = .001, .5, .1
        lo = [(-width / 2, -gap / 2), (width / 2, -gap / 2), (width / 2, -gap / 2 - height),
              (-width / 2, -gap / 2 - height), (-width / 2, -gap / 2)]
        hi = [(x, -y) for x, y in lo][::-1]

        def segment(name, points):
            lines = [f"Segment: {name} 2", "properties: 2 8 0 0 0"]
            lines += [f"{a!r} {b!r} {c!r} {d!r}" for (a, b), (c, d) in zip(points[:-1], points[1:])]
            return "\n".join(lines)
        text = ("Title: t\n" + segment('lo', lo) + "\n\n" + segment('hi', hi)
                + "\n\nIBCS_Resistances:\n\nDielectrics:\n")

        def solve():
            with contextlib.redirect_stdout(io.StringIO()):
                result = solve_monostatic_rcs_2d(build_geometry_snapshot(*parse_geometry(text)), [10.0],
                                                 [0., 45., 90.], geometry_units='inches')
            return np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in result['samples']])
        new = solve()
        with mock.patch.object(thin_gap, 'THIN_GAP', 0.):
            old = solve()
        self.assertLess(np.max(np.abs(new - old) / np.abs(old)), 1e-9)


if __name__ == '__main__':
    unittest.main()
