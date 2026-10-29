"""Regressions for the tolerance envelope, sweep endpoints, inverse fast path,
vectorized Bruggeman, Material Mix seeding and free-space-backed export."""
from __future__ import annotations

import math
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import ibc.compute as compute
from ibc.compute import (
    C0,
    ConstantMaterial,
    INCH_TO_M,
    LoadedLayer,
    MIX_RULE_BRUGGEMAN,
    MaterialTable,
    UNCERTAINTY_AXIS_SAMPLES,
    UncertaintyConfig,
    build_uncertainty_scales,
    combine_mix,
    compute_angle_metrics_many,
    compute_metal_loss_db_many,
    compute_stack_impedance_many,
    describe_uncertainty_sampling,
    make_frequency_sweep,
    make_sweep,
    prepare_layer_properties_many,
    prepare_layer_wave_terms_many,
    validate_sweep_coverage,
)
from ibc.design_search import MixSearchRequest, run_mix_search, score_inverse_candidate
from ibc.io import (
    FREE_SPACE_IMPEDANCE_HEADER,
    IMPEDANCE_HEADER,
    IMPEDANCE_UNCERTAINTY_HEADER,
    write_impedance_bundle,
)
from ibc.sweep_admission import sweep_count


def _quarter_wave_layer():
    eps = 4 - 0.2j
    thickness = C0 / (4 * 10e9 * 2)
    return [LoadedLayer(thickness, False, 0, ConstantMaterial(eps, 1 + 0j), None)]


class ToleranceEnvelopeTests(unittest.TestCase):
    def test_interior_resonance_is_inside_the_sampled_envelope(self):
        layers = _quarter_wave_layer()
        dense = [
            compute_stack_impedance_many([10.0], layers, "pec", thickness_scale=t)[0]
            for t in np.linspace(0.9, 1.1, 4001)
        ]
        scales = build_uncertainty_scales(UncertaintyConfig(True, 10, 0, 0))
        sampled = [
            compute_stack_impedance_many([10.0], layers, "pec", thickness_scale=t,
                                         eps_scale=e, mu_scale=m)[0]
            for t, e, m in scales
        ]
        true_lo = min(z.imag for z in dense)
        true_hi = max(z.imag for z in dense)
        # Corners alone gave X in [-1093, 1140] ohm against [-2277, 2517].
        self.assertLess(min(z.imag for z in sampled), 0.95 * true_lo)
        self.assertGreater(max(z.imag for z in sampled), 0.95 * true_hi)

    def test_case_set_contains_corners_axes_and_nominal(self):
        scales = build_uncertainty_scales(UncertaintyConfig(True, 5, 5, 5))
        self.assertIn((1.0, 1.0, 1.0), scales)
        for corner in [(t, e, m) for t in (.95, 1.05) for e in (.95, 1.05) for m in (.95, 1.05)]:
            self.assertIn(corner, scales)
        axis_points = UNCERTAINTY_AXIS_SAMPLES - 1  # excluding nominal
        self.assertEqual(len(scales), 8 + 1 + 3 * axis_points)
        self.assertEqual(len(set(scales)), len(scales))
        only_t = build_uncertainty_scales(UncertaintyConfig(True, 10, 0, 0))
        self.assertEqual(len(only_t), UNCERTAINTY_AXIS_SAMPLES)
        self.assertEqual(min(only_t), (0.9, 1.0, 1.0))
        self.assertEqual(max(only_t), (1.1, 1.0, 1.0))
        self.assertEqual(build_uncertainty_scales(UncertaintyConfig(False, 5, 5, 5)),
                         [(1.0, 1.0, 1.0)])

    def test_sidecar_states_what_the_envelope_samples(self):
        cfg = UncertaintyConfig(True, 10, 0, 0)
        note = describe_uncertainty_sampling(cfg)
        self.assertIn(f"{UNCERTAINTY_AXIS_SAMPLES} evenly spaced points", note)
        self.assertIn(f"{len(build_uncertainty_scales(cfg))} sampled cases", note)
        with tempfile.TemporaryDirectory() as tmp:
            nominal = Path(tmp) / "z.csv"
            sidecar = Path(tmp) / "z_uncertainty.csv"
            write_impedance_bundle(
                nominal, [(1.0, 100.0, 5.0)], sidecar,
                [(1.0, 100.0, 5.0, 90.0, 110.0, 0.0, 10.0)], uncertainty_note=note,
            )
            lines = sidecar.read_text(encoding="utf-8").splitlines()
            self.assertTrue(lines[0].startswith("# Tolerance envelope"))
            self.assertEqual(lines[1], IMPEDANCE_UNCERTAINTY_HEADER)
            self.assertEqual(nominal.read_text(encoding="utf-8").splitlines()[0],
                             IMPEDANCE_HEADER)


class SweepEndpointTests(unittest.TestCase):
    def test_last_point_snaps_to_stop(self):
        sweep = make_sweep(0.1, 0.3, 0.1)
        self.assertEqual(len(sweep), 3)
        self.assertEqual(sweep[-1], 0.3)
        table = MaterialTable([0.1, 0.3], [2 + 0j, 2 + 0j], [1 + 0j, 1 + 0j])
        validate_sweep_coverage(sweep, table, "layer")  # previously refused

    def test_large_counts_keep_the_stop_point(self):
        self.assertEqual(sweep_count(1.0, 2.0, 1e-5), 100001)
        sweep = make_frequency_sweep(1.0, 2.0, 1e-5)
        self.assertEqual(len(sweep), 100001)
        self.assertEqual(sweep[-1], 2.0)
        self.assertTrue(all(b > a for a, b in zip(sweep, sweep[1:])))

    def test_off_step_stop_is_still_excluded(self):
        self.assertEqual(sweep_count(0.0, 1.0, 0.3), 4)
        self.assertAlmostEqual(make_sweep(0.0, 1.0, 0.3)[-1], 0.9)
        self.assertEqual(sweep_count(1.0, 1.0, 0.1), 1)


class InverseFastPathTests(unittest.TestCase):
    def setUp(self):
        self.freqs = list(np.round(np.arange(2, 18.0001, 0.4), 6))
        tab = MaterialTable([1., 20.], [12 - .6j, 10 - .5j], [2 - 1.5j, 1.2 - .6j])
        tab2 = MaterialTable([1., 20.], [4 - .1j, 4 - .1j], [1, 1])
        self.layers = lambda t1: [
            LoadedLayer(0, False, 0, None, None, True, 300.),
            LoadedLayer(t1 * INCH_TO_M, False, 0, tab2, None),
            LoadedLayer(.05 * INCH_TO_M, False, 0, tab, None),
        ]

    def test_metal_only_matches_full_metrics_bitwise(self):
        layers = self.layers(.1)
        for pol in ("te", "tm"):
            for angle in (0., 40.):
                full = compute_angle_metrics_many(self.freqs, angle, layers, pol,
                                                  thickness_scale=1.03, eps_scale=.97)
                fast = compute_metal_loss_db_many(self.freqs, angle, layers, pol,
                                                  thickness_scale=1.03, eps_scale=.97)
                self.assertEqual(list(fast), full["metal_loss_db"])

    def test_score_is_identical_to_the_full_metric_path(self):
        scales = build_uncertainty_scales(UncertaintyConfig(True, 5, 5, 5))
        angles = [0., 30.]
        ref = self.layers(.1)
        props = prepare_layer_properties_many(self.freqs, ref)
        prepared = {}
        for _t, e, m in scales:
            for a in angles:
                prepared.setdefault((a, e, m), prepare_layer_wave_terms_many(
                    self.freqs, a, ref, "te", eps_scale=e, mu_scale=m,
                    prepared_properties=props))
        stats = lambda v: (sum(v) / len(v), min(v), max(v))
        legacy = lambda *a, **k: compute_angle_metrics_many(*a, **k)
        for t1 in (.08, .1, .13):
            for mode in ("Worst case", "Average"):
                common = dict(stop_requested=lambda: False, statistics=stats)
                fast = score_inverse_candidate(self.freqs, angles, self.layers(t1), "te",
                                               scales, mode, prepared, **common)
                slow = score_inverse_candidate(self.freqs, angles, self.layers(t1), "te",
                                               scales, mode, prepared,
                                               compute_metrics=legacy, **common)
                self.assertEqual(fast, slow)

    def test_prepared_terms_for_another_sweep_are_refused(self):
        ref = self.layers(.1)
        terms = prepare_layer_wave_terms_many(self.freqs, 0., ref, "te")
        with self.assertRaisesRegex(ValueError, "frequency sweep"):
            compute_metal_loss_db_many(self.freqs[:-1], 0., ref, "te",
                                       prepared_wave_terms=terms)


def _scalar_bruggeman(cols, fractions):
    with mock.patch.object(compute, "NUMPY_AVAILABLE", False):
        return compute._combine_columns(cols, fractions, MIX_RULE_BRUGGEMAN)


class BruggemanVectorTests(unittest.TestCase):
    def test_vector_path_matches_scalar_path(self):
        rng = random.Random(2024)

        def rand_z():
            re = 10 ** rng.uniform(-0.3, 2.5)
            im = -10 ** rng.uniform(-4, 3) if rng.random() < 0.8 else 0.0
            return complex(-re if rng.random() < 0.05 else re, im)

        checked = 0
        for _ in range(300):
            k = rng.choice([2, 3, 4])
            n = rng.choice([1, 7, 30])
            base = [rand_z() for _ in range(k)]
            slope = [rand_z() * rng.uniform(0, .05) for _ in range(k)]
            cols = [[complex((b + s * i).real, min((b + s * i).imag, 0.)) for i in range(n)]
                    for b, s in zip(base, slope)]
            if rng.random() < 0.2:
                cols[1] = list(cols[0])
            raw = [rng.random() for _ in range(k)]
            fractions = [r / sum(raw) for r in raw]
            try:
                old = _scalar_bruggeman(cols, fractions)
            except ValueError:
                continue
            new = compute._combine_columns(cols, fractions, MIX_RULE_BRUGGEMAN)
            # The 2-component closed form is the exact root; the scalar
            # Newton stops at residual 1e-11, so allow its truncation error.
            tol = 1e-12 if k > 2 else 1e-9
            for a, b in zip(old, new):
                self.assertLessEqual(abs(a - b), tol * abs(a), (cols, fractions))
            checked += 1
        self.assertGreater(checked, 250)

    def test_reference_two_phase_roots(self):
        for host, inc, f in [(2.5 - .01j, 12 - 1.2j, .2), (3 - .05j, 1 - 5000j, .33),
                             (1.0 + 0j, 40 - 30j, .5)]:
            b = (3 * (1 - f) - 1) * host + (3 * f - 1) * inc
            r = complex(np.sqrt(b * b + 8 * host * inc))
            roots = [(b + r) / 4, (b - r) / 4]
            physical = min((z for z in roots if z.imag <= 1e-12), key=lambda z: -z.real)
            got = combine_mix([1.], [[host], [inc]], [[1 + 0j], [1 + 0j]], [1 - f, f],
                              "bruggeman").eps_r[0]
            self.assertLess(abs(got - physical), 1e-12 * abs(physical))

    def test_identical_constituents_short_circuit_exactly(self):
        cols = [[1 + 0j] * 5, [1 + 0j] * 5, [1 + 0j] * 5]
        self.assertEqual(compute._combine_columns(cols, [.2, .3, .5], MIX_RULE_BRUGGEMAN),
                         [1 + 0j] * 5)

    def test_lossless_constituents_return_the_positive_root(self):
        # Both roots are real (40.0 and -9.39); the residual-noise ranking
        # alone could return the unphysical negative one.
        for path in (compute._combine_columns, None):
            cols = [[3.0862364359574865 + 0j], [243.40633216356488 + 0j]]
            fractions = [0.5860086414983398, 0.41399135850166024]
            value = (_scalar_bruggeman(cols, fractions) if path is None else
                     path(cols, fractions, MIX_RULE_BRUGGEMAN))[0]
            self.assertAlmostEqual(value.real, 40.00717038364233, places=9)

    def test_three_component_sweep_is_fast(self):
        n = 801
        grid = list(np.linspace(1, 18, n))
        eps = [[2.5 - .01j] * n, [12 - 1.2j] * n, [1 - 500j] * n]
        mu = [[1 + 0j] * n, [2 - 1j] * n, [1 + 0j] * n]
        import time
        start = time.perf_counter()
        combine_mix(grid, eps, mu, [.6, .3, .1], "bruggeman")
        self.assertLess(time.perf_counter() - start, 0.1)  # was ~165 ms


class MixSeedTests(unittest.TestCase):
    def request(self, seed):
        return MixSearchRequest(
            UncertaintyConfig(False, 0., 0., 0.),
            [{"file": "a.csv", "parts": 1., "density": 1.},
             {"file": "b.csv", "parts": 1., "density": 1.}],
            [1., 2.], "linear", True, False,
            {"freqs": [1., 2.], "eps": [6. - .1j] * 2, "mu": [1 + 0j] * 2,
             "w_eps": 1., "w_mu": 1.},
            .125, None, "Worst-case", seed, [0., 0.], [1., 1.], 40, 3,
            False, "constant target", "1 and 2 GHz", True)

    def run_search(self, seed):
        tables = {"a.csv": MaterialTable([1., 2.], [4 + 0j] * 2, [1 + 0j] * 2),
                  "b.csv": MaterialTable([1., 2.], [9 + 0j] * 2, [1 + 0j] * 2)}
        return run_mix_search(self.request(seed), read_table=lambda p: tables[p.name])

    def test_blank_seed_is_generated_reported_and_reproducible(self):
        candidates, _, message = self.run_search(None)
        line = next(l for l in message.splitlines() if l.startswith("Random seed:"))
        self.assertIn("generated", line)
        seed = int(line.split(":")[1].split()[0].rstrip("."))
        again, _, message2 = self.run_search(seed)
        self.assertEqual([c.fractions for c in candidates], [c.fractions for c in again])
        self.assertIn(f"Random seed: {seed}.", message2)


class FreeSpaceExportTests(unittest.TestCase):
    def test_free_space_backed_output_has_a_distinct_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            pec = Path(tmp) / "pec.csv"
            air = Path(tmp) / "air.csv"
            rows = [(1.0, 120.0, 15.0), (2.0, 110.0, 12.0)]
            write_impedance_bundle(pec, rows)
            write_impedance_bundle(air, rows, backing="air")
            self.assertEqual(pec.read_text(encoding="utf-8").splitlines()[0], IMPEDANCE_HEADER)
            air_lines = air.read_text(encoding="utf-8").splitlines()
            self.assertTrue(air_lines[0].startswith("#"))
            self.assertEqual(air_lines[1], FREE_SPACE_IMPEDANCE_HEADER)
            try:
                ghost_root = Path(__file__).resolve().parents[2] / "GHOST"
                sys.path.insert(0, str(ghost_root))
                from ghost_backend.twod.geometry import _load_impedance_csv
            except Exception as exc:  # GHOST not importable in this checkout
                self.skipTest(f"GHOST loader unavailable: {exc}")
            finally:
                if sys.path and sys.path[0] == str(ghost_root):
                    sys.path.pop(0)
            self.assertEqual(len(_load_impedance_csv(str(pec)).values), 2)
            with self.assertRaisesRegex(ValueError, "resistance_ohm,reactance_ohm"):
                _load_impedance_csv(str(air))


if __name__ == "__main__":
    unittest.main()
