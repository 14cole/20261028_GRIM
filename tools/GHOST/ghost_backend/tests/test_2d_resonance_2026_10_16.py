"""Regressions for the October 16 2-D accuracy audit (R1, R2, R4, N1).

R1: the exterior of a partial coating (open TYPE 2/3/4 junctions) is combined
    S + gamma*D; its interior Dirichlet resonance is gone.
R2: closed PEC loops of a separated sheet + PEC scene are combined.
R4: certificates estimate the published (fine) error, delta/(r - 1).
N1: the condition gate of combined formulations is frequency aware.
"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.twod import solver as td
from ghost_backend.twod.formulations import combined_regions, sheet
from ghost_backend.runs.quality import estimated_published_error
from ghost_backend.validation.cylinder import sigma_dielectric_cylinder, sigma_pec_cylinder

DENSE = dict(factorization='dense', mesh_strategy='global')
RADIUS = .1
# First interior Dirichlet zero of the partial-coating outline (114 panels),
# located by the former equation's condition peak.
PARTIAL_RESONANCE_KA = 2.8688


def _pairs(points):
    return [dict(x1=float(a[0]), y1=float(a[1]), x2=float(b[0]), y2=float(b[1]))
            for a, b in zip(points[:-1], points[1:])]


def _segment(name, seg_type, points, panels=0, ibc=0, plus=0, minus=0):
    return dict(name=name, seg_type=seg_type, point_pairs=_pairs(points),
                properties=[str(seg_type), str(panels), str(ibc), str(plus), str(minus)])


def _arc(radius, start, stop, count):
    theta = np.linspace(start, stop, count+1)
    points = [(radius*np.cos(t), radius*np.sin(t)) for t in theta]
    points[0] = tuple(round(v, 12) for v in points[0])
    points[-1] = tuple(round(v, 12) for v in points[-1])
    return points


def _dielectric(flag, eps):
    eps = complex(eps)
    return [str(flag), repr(eps.real), repr(eps.imag), '1.0', '0.0']


def partial_coating(panels=0, eps=3.0):
    """PEC core r = 0.07 m, bare upper half, lower half coated to r = 0.1 m."""
    upper = _arc(.07, np.pi, 0, 32); upper[0], upper[-1] = (-.07, 0.), (.07, 0.)
    core = _arc(.07, 0, -np.pi, 32); core[0], core[-1] = (.07, 0.), (-.07, 0.)
    outer = _arc(.1, 0, -np.pi, 48); outer[0], outer[-1] = (.1, 0.), (-.1, 0.)
    segments = [_segment('bare', 2, upper), _segment('r1', 3, [(.07, 0.), (.1, 0.)], plus=1),
                _segment('outer', 3, outer, plus=1), _segment('r2', 3, [(-.1, 0.), (-.07, 0.)], plus=1),
                _segment('core', 4, core, plus=1)]
    for segment in segments:
        segment['properties'][1] = str(panels)
    return dict(segments=segments, ibcs=[], dielectrics=[_dielectric(1, eps)])


def split_disk(eps=4.0, count=48):
    """A homogeneous disk split by a TYPE 5 diameter into two regions of one material."""
    return dict(segments=[_segment('up', 3, _arc(RADIUS, np.pi, 0, count), plus=1),
                          _segment('lo', 3, _arc(RADIUS, 0, -np.pi, count), plus=2),
                          _segment('dia', 5, [(-RADIUS, 0.), (RADIUS, 0.)], plus=1, minus=2)],
                ibcs=[], dielectrics=[_dielectric(1, eps), _dielectric(2, eps)])


def pec_and_sheet(impedance=1e7, closed=True):
    circle = _arc(RADIUS, 0, -2*np.pi, 96); circle[-1] = circle[0]
    body = (_segment('c', 2, circle) if closed else
            _segment('c', 2, [(-RADIUS, -.05), (-RADIUS, .05)], panels=8))
    return dict(segments=[body, _segment('sh', 1, [(.3, -.05), (.3, .05)], panels=4, ibc=1)],
                ibcs=[['1', 'constant', repr(float(impedance)), '0', '0', '0']], dielectrics=[])


def _frequency_ghz(ka, radius=RADIUS):
    return ka*td.C0/(2*np.pi*radius)/1e9


def _solve(shape, pol, ka, angles=(0., 90.), **kwargs):
    kwargs.setdefault('strict_quality_gate', False)
    result = td.solve_monostatic_rcs_2d_single_polarization(shape, [_frequency_ghz(ka)], list(angles), pol,
        geometry_units='meters', compute_condition_number=True, execution_options=dict(DENSE), **kwargs)
    amplitude = np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in result['samples']])
    return amplitude, np.array([s['rcs_linear'] for s in result['samples']]), result['metadata']


def _former_equation():
    """The former eligibility: no union-closed region is combined."""
    return patch.object(combined_regions, '_union_junctions', lambda *args, **kwargs: None)


class PartialCoatingResonanceTests(unittest.TestCase):
    def test_exterior_is_combined_and_coating_stays_single_layer(self):
        from ghost_backend.twod.formulations.regions import build_layout
        shape = partial_coating()
        frequency = _frequency_ghz(2.0)
        mesh, infos = _mesh_and_infos(shape, frequency, 'TM')
        layout = build_layout(mesh, infos, 'TM')
        coupled = combined_regions.couplings(mesh, layout)
        exterior = [rid for rid, region in layout['region_props'].items() if region['has_incident']]
        self.assertEqual(set(layout['combined_junctions']), set(exterior))
        self.assertEqual({rid for _, rid in coupled}, set(exterior))
        self.assertEqual(len(layout['combined_junctions'][exterior[0]]), 2)

    def test_resonance_removed_and_fields_converge(self):
        for pol in ('TE', 'TM'):
            with self.subTest(pol=pol):
                coarse, _, meta = _solve(partial_coating(panels=1), pol, PARTIAL_RESONANCE_KA)
                fine, _, _ = _solve(partial_coating(panels=4), pol, PARTIAL_RESONANCE_KA)
                with _former_equation():
                    former, _, former_meta = _solve(partial_coating(panels=1), pol, PARTIAL_RESONANCE_KA)
                scale = np.max(np.abs(fine))
                self.assertLess(meta['condition_est_max'], 1e4)
                self.assertGreater(former_meta['condition_est_max'], 1e4)
                self.assertLess(np.max(np.abs(coarse - fine))/scale, 1e-2)
                self.assertGreater(np.max(np.abs(former - fine))/scale, 5e-2)
                self.assertIn('exterior closed by open-junction arcs', meta['formulation'])

    def test_off_resonance_matches_former_equation(self):
        for pol in ('TE', 'TM'):
            new, _, _ = _solve(partial_coating(), pol, 2.0)
            with _former_equation():
                former, _, _ = _solve(partial_coating(), pol, 2.0)
            self.assertLess(np.max(np.abs(new - former))/np.max(np.abs(former)), 2e-3)

    def test_split_disk_matches_exact_cylinder(self):
        # Two regions of one material: the exterior closes through two open
        # arcs; ka = 2.4048 is the circle's first interior Dirichlet zero.
        for ka in (1.0, 2.4048):
            for pol in ('TE', 'TM'):
                with self.subTest(ka=ka, pol=pol):
                    _, sigma, meta = _solve(split_disk(), pol, ka, angles=(0.,))
                    exact = sigma_dielectric_cylinder(RADIUS, 4.0, 1.0, _frequency_ghz(ka)*1e9, pol)
                    self.assertLess(abs(sigma[0]/exact - 1), 2e-2)
                    self.assertLess(meta['condition_est_max'], 1e4)

    def test_compressed_coefficients_match_dense(self):
        dense, _, _ = _solve(partial_coating(), 'TM', PARTIAL_RESONANCE_KA)
        with patch.dict('os.environ', {'GHOST_CPU_FACTORIZATION': 'compressed'}):
            compressed, _, meta = _solve_compressed()
        self.assertIn('compressed', meta['solver_method'])
        self.assertLess(np.max(np.abs(compressed - dense))/np.max(np.abs(dense)), 1e-6)


def _solve_compressed():
    result = td.solve_monostatic_rcs_2d_single_polarization(partial_coating(), [_frequency_ghz(PARTIAL_RESONANCE_KA)],
        [0., 90.], 'TM', geometry_units='meters', strict_quality_gate=False)
    return np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in result['samples']]), None, result['metadata']


def _mesh_and_infos(shape, frequency_ghz, pol):
    captured = {}
    from ghost_backend.twod.formulations import regions
    original = regions.assemble_system

    def capture(mesh, infos, polarization, *args, **kwargs):
        captured.setdefault('value', (mesh, infos))
        return original(mesh, infos, polarization, *args, **kwargs)
    with patch.object(regions, 'assemble_system', capture):
        td.solve_monostatic_rcs_2d_single_polarization(shape, [frequency_ghz], [0.], pol,
            geometry_units='meters', strict_quality_gate=False, execution_options=dict(DENSE))
    return captured['value']


class SheetPecResonanceTests(unittest.TestCase):
    def test_closed_conductor_is_combined_at_its_resonances(self):
        for pol, ka in (('TM', 2.4057), ('TE', 3.0542), ('TM', 3.8317), ('TE', 3.8317)):
            with self.subTest(pol=pol, ka=ka):
                _, sigma, meta = _solve(pec_and_sheet(), pol, ka, angles=(0.,))
                with patch.object(sheet, 'pec_combination', lambda *args, **kwargs: None):
                    _, former, former_meta = _solve(pec_and_sheet(), pol, ka, angles=(0.,))
                exact = sigma_pec_cylinder(RADIUS, _frequency_ghz(ka)*1e9, pol)
                self.assertLess(meta['condition_est_max'], 1e3)
                self.assertGreater(former_meta['condition_est_max'], 3e3)
                self.assertLess(abs(sigma[0]/exact - 1), 2e-2)
                self.assertIn('combined', meta['formulation'])

    def test_interacting_sheet_agrees_with_former_equation(self):
        for pol in ('TE', 'TM'):
            new, _, _ = _solve(pec_and_sheet(100.), pol, 2.0, angles=(0., 60., 180.))
            with patch.object(sheet, 'pec_combination', lambda *args, **kwargs: None):
                former, _, _ = _solve(pec_and_sheet(100.), pol, 2.0, angles=(0., 60., 180.))
            self.assertLess(np.max(np.abs(new - former))/np.max(np.abs(former)), 1e-3)

    def test_bistatic_backscatter_matches_monostatic(self):
        for pol in ('TE', 'TM'):
            mono, _, _ = _solve(pec_and_sheet(100.), pol, 2.0, angles=(30.,))
            result = td.solve_bistatic_rcs_2d_single_polarization(pec_and_sheet(100.), [_frequency_ghz(2.0)],
                [30.], [30.], pol, geometry_units='meters', strict_quality_gate=False,
                execution_options=dict(DENSE))
            bistatic = complex(result['samples'][0]['rcs_amp_real'], result['samples'][0]['rcs_amp_imag'])
            self.assertLess(abs(bistatic - mono[0])/abs(mono[0]), 1e-6)

    def test_open_conductor_warns_without_protection(self):
        _, _, meta = _solve(pec_and_sheet(closed=False), 'TM', 2.0)
        self.assertNotIn('combined', meta['formulation'])
        self.assertTrue(any('not protected against fictitious interior resonances' in w
                            for w in meta['warnings']))


class PublishedErrorEstimateTests(unittest.TestCase):
    def test_estimate_uses_first_order_richardson(self):
        record = estimated_published_error(dict(complex_max_normalized=.01, rms_db=.1), 1.5)
        self.assertTrue(record['available'])
        self.assertAlmostEqual(record['factor'], 2.0)
        self.assertAlmostEqual(record['complex_max_normalized'], .02)
        self.assertAlmostEqual(record['rms_db'], .2)
        self.assertFalse(estimated_published_error(dict(complex_max_normalized=.01), 1.0)['available'])

    def test_certificate_reports_estimate(self):
        circle = _arc(RADIUS, 0, -2*np.pi, 64); circle[-1] = circle[0]
        result = td.solve_monostatic_rcs_2d_certified(dict(segments=[_segment('c', 2, circle)], ibcs=[], dielectrics=[]),
            [_frequency_ghz(2.0)], [0., 90.], geometry_units='meters', execution_options=dict(DENSE))
        for channel in ('VV', 'HH'):
            mesh = result['metadata']['channel_metadata'][channel]['mesh_convergence']
            ratio = mesh['panel_refinement_ratio']
            self.assertAlmostEqual(mesh['estimated_published_complex_max_normalized'],
                                   mesh['complex_max_normalized']/(ratio - 1))
            self.assertEqual(mesh['estimated_published_error']['assumed_order'], 1.0)
        self.assertIn('estimated_published_complex_max_normalized', result['metadata']['mesh_convergence'])
        from ghost_backend.runs.quality import solver_report_text
        self.assertIn('Estimated error of the published (fine) result',
                      solver_report_text(result['metadata']['channel_metadata']['VV']))


class FrequencyAwareConditionGateTests(unittest.TestCase):
    def test_low_frequency_dielectric_passes_strict_gate(self):
        circle = _arc(RADIUS, 0, -2*np.pi, 128); circle[-1] = circle[0]
        shape = dict(segments=[_segment('d', 3, circle, plus=1)], ibcs=[], dielectrics=[_dielectric(1, 4-1j)])
        _, sigma, meta = _solve(shape, 'TE', 3e-4, angles=(0.,), strict_quality_gate=True)
        exact = sigma_dielectric_cylinder(RADIUS, 4-1j, 1.0, _frequency_ghz(3e-4)*1e9, 'TE')
        self.assertGreater(meta['condition_est_max'], 1e6)
        self.assertLess(meta['condition_est_frequency_scaled_max'], 1e4)
        self.assertTrue(meta['quality_gate']['passed'])
        self.assertLess(abs(sigma[0]/exact - 1), 2e-3)

    def test_scaled_gate_still_rejects_ill_conditioning(self):
        base = dict(residual_norm_max=1e-12, condition_est_computed=True, warnings=[])
        self.assertTrue(td.evaluate_quality_gate(dict(base, condition_est_max=2e6,
            condition_est_frequency_scaled_max=2e3))['passed'])
        gate = td.evaluate_quality_gate(dict(base, condition_est_max=1e10,
            condition_est_frequency_scaled_max=1e7))
        self.assertFalse(gate['passed'])
        self.assertIn('frequency-scaled', gate['reason'] if 'reason' in gate else ' '.join(gate['violations']))
        self.assertFalse(td.evaluate_quality_gate(dict(base, condition_est_max=2e6))['passed'])

    def test_scale_is_unity_above_the_low_frequency_range(self):
        circle = _arc(RADIUS, 0, -2*np.pi, 16); circle[-1] = circle[0]
        _, _, meta = _solve(dict(segments=[_segment('c', 2, circle)], ibcs=[], dielectrics=[]), 'TE', 2.0)
        self.assertEqual(meta['condition_est_frequency_scaled_max'], meta['condition_est_max'])


if __name__ == '__main__':
    unittest.main()


class BalancedConditionEstimateTests(unittest.TestCase):
    """Union-combined systems: block-balanced condition estimate (airfoil regression)."""

    def test_union_systems_use_the_balanced_estimate(self):
        _, _, meta = _solve(partial_coating(), 'TE', 2.0)
        self.assertTrue(meta['condition_estimator'].endswith('_block_balanced'))
        circle = _arc(RADIUS, 0, -2*np.pi, 32); circle[-1] = circle[0]
        _, _, closed = _solve(dict(segments=[_segment('c', 3, circle, plus=1)], ibcs=[],
                                   dielectrics=[_dielectric(1, 3.)]), 'TE', 2.0)
        self.assertFalse(closed['condition_estimator'].endswith('_block_balanced'))

    def test_balance_keeps_a_genuine_resonance(self):
        from ghost_backend.twod.formulations import regions
        from ghost_backend.twod.formulations.combined_regions import balanced_condition_scaling
        captured = {}
        original = regions.assemble_system

        def capture(mesh, infos, pol, *args, **kwargs):
            matrix, layout = original(mesh, infos, pol, *args, **kwargs)
            captured['value'] = (np.array(matrix), layout)
            return matrix, layout
        with _former_equation(), patch.object(regions, 'assemble_system', capture):
            _solve(partial_coating(panels=4), 'TE', 2.869)
        matrix, layout = captured['value']
        starts = sorted(offset for offset, _ in layout['dof_map'].values())
        scaling = td._equilibrated_scaling_and_norm_1(matrix)
        for rows, columns, norm in (scaling, balanced_condition_scaling(matrix, scaling, starts)):
            balanced = matrix/rows[:, None]/columns[None, :]
            self.assertAlmostEqual(norm, np.abs(balanced).sum(0).max(), delta=1e-9*norm)
            self.assertGreater(np.linalg.cond(balanced, 1), 5e5)
