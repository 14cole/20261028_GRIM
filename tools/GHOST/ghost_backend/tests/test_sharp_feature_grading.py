"""Geometric mesh grading toward sharp edges, tips and open ends (2-D and BoR meridians)."""
from pathlib import Path
import math
import sys
import unittest
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.twod import geometry as tg
from ghost_backend.twod import solver as td
from ghost_backend.bor import dispatch, solver as bor

DIEL = ['1', '4.0', '-0.4', '1.0', '0.0']


def _segment(points, seg_type=2, n=0, ibc=0, pos=0, neg=0, name='s'):
    return dict(name=name, seg_type=seg_type, properties=[str(seg_type), str(n), str(ibc), str(pos), str(neg)],
                point_pairs=[dict(x1=float(a[0]), y1=float(a[1]), x2=float(b[0]), y2=float(b[1]))
                             for a, b in zip(points[:-1], points[1:])])


def _snapshot(*segments, ibcs=(), dielectrics=()):
    return dict(segments=list(segments), ibcs=list(ibcs), dielectrics=list(dielectrics))


def _square(side=.3):
    return [(0., 0.), (0., side), (side, side), (side, 0.), (0., 0.)]   # clockwise: normal into air


def _polygon(count, radius=.15):
    angles = -2*np.pi*np.arange(count+1)/count
    points = [(radius*math.cos(a), radius*math.sin(a)) for a in angles]
    points[-1] = points[0]
    return points


def _rhombus(tip_deg, chord=.3):
    t = .5*chord*math.tan(math.radians(tip_deg)/2)
    return [(chord/2, 0.), (0., -t), (-chord/2, 0.), (0., t), (chord/2, 0.)]


def _panels(snapshot, frequency=1., scale=1., **kwargs):
    materials = tg.MaterialLibrary.from_entries(snapshot['ibcs'], snapshot['dielectrics'], base_dir='')
    wavelength = tg._mesh_wavelength_for_snapshot(snapshot, materials, frequency)[0]
    return tg._build_panels(snapshot, scale, wavelength, materials=materials, frequencies_ghz=[frequency], **kwargs)


def _ungraded(snapshot, **kwargs):
    with patch.object(tg, 'SHARP_GRADING_MAX_EXPONENT', 0.):
        return _panels(snapshot, **kwargs)


def _exponents(snapshot, frequency=1.):
    found = {}
    original = tg._sharp_vertices
    def spy(*args, **kwargs):
        result = original(*args, **kwargs)
        found.update(result)
        return result
    with patch.object(tg, '_sharp_vertices', spy):
        _panels(snapshot, frequency)
    return sorted(round(nu, 4) for nu, _ in found.values())


def _geometry(panels):
    return np.array([[*p.p0, *p.p1] for p in panels])


class SingularExponentTests(unittest.TestCase):
    def test_a_lone_conductor_sector_has_the_wedge_exponent(self):
        for alpha in (1.5*np.pi, 2*np.pi, 1.2*np.pi):
            for pol in ('TM', 'TE'):
                self.assertAlmostEqual(tg._wedge_exponent([(alpha, 1.)], True, pol), np.pi/alpha, places=12)
        self.assertEqual(tg._wedge_exponent([(.5*np.pi, 1.)], True, 'TM'), 1.)    # re-entrant field corner

    def test_penetrable_sectors_solve_the_angular_eigenproblem(self):
        # dielectric square corner (eps 4 inside 90 degrees): TE singular, TM regular (mu = 1)
        sectors = lambda k: [(.5*np.pi, k), (1.5*np.pi, 1.)]
        self.assertAlmostEqual(tg._wedge_exponent(sectors(1/4.), False, 'TE'), .806, places=3)
        self.assertEqual(tg._wedge_exponent(sectors(1.), False, 'TM'), 1.)
        # a high-contrast dielectric corner tends to the conductor exponent 2/3
        self.assertAlmostEqual(tg._wedge_exponent(sectors(1e-4), False, 'TE'), 2/3, places=2)
        # PEC half plane split into two media (feathered coating): regular, nu = 1
        self.assertEqual(tg._wedge_exponent([(np.pi - .1, 1.), (.1, 1/4.)], True, 'TE'), 1.)

    def test_vertices_are_classified_from_the_drawn_boundary(self):
        self.assertEqual(_exponents(_snapshot(_segment(_square()))), [.6667]*4)
        self.assertEqual(_exponents(_snapshot(_segment([(0., 0.), (.3, 0.)]))), [.5]*2)              # open strip
        self.assertEqual(_exponents(_snapshot(_segment([(0., 0.), (.3, 0.)], seg_type=1))), [.5]*2)  # sheet ends
        self.assertEqual(_exponents(_snapshot(_segment(_rhombus(1.)))), [.5014]*2)   # two tips, obtuse corners drawn as a curve
        self.assertEqual(_exponents(_snapshot(_segment(_polygon(24)))), [])          # 15 degree turns: a drawn curve
        self.assertEqual(_exponents(_snapshot(_segment(_polygon(18)))), [])          # 20 degree turns: nu = 0.9
        self.assertEqual(_exponents(_snapshot(_segment(_polygon(12)))), [.8571]*12)
        self.assertEqual(_exponents(_snapshot(_segment(_square(), seg_type=3, pos=1), dielectrics=[DIEL])), [.8055]*4)   # |eps| = 4.02

    def test_a_plate_thinner_than_its_panels_grades_like_a_knife_edge(self):
        plate = [(0., 0.), (0., 2.5e-5), (.3, 2.5e-5), (.3, 0.), (0., 0.)]
        nus = _exponents(_snapshot(_segment(plate)))
        self.assertEqual(len(nus), 4)
        self.assertTrue(all(.5 <= nu < .51 for nu in nus))


class GradedMeshTests(unittest.TestCase):
    def test_smooth_bodies_keep_their_meshes_bit_for_bit(self):
        coated = _snapshot(_segment(_polygon(96, .12), seg_type=3, pos=1), _segment(_polygon(80, .1), seg_type=4, pos=1),
                           dielectrics=[DIEL])
        for snapshot in (_snapshot(_segment(_polygon(64))), _snapshot(_segment(_polygon(24), n=3)), coated):
            np.testing.assert_array_equal(_geometry(_panels(snapshot)), _geometry(_ungraded(snapshot)))

    def test_corner_panels_halve_down_to_the_singular_depth(self):
        snapshot = _snapshot(_segment(_square(), n=10))
        panels = _panels(snapshot)
        self.assertEqual(len(panels), len(_ungraded(snapshot)) + 4*2*2)       # two levels per side of each corner
        lengths = sorted({round(p.length/.03, 9) for p in panels})
        self.assertEqual(lengths, [.25, .5, 1.])
        # a knife edge takes the impedance-junction depth (four levels at <= 32 panels per wavelength)
        strip = _panels(_snapshot(_segment([(0., 0.), (.3, 0.)], n=10)))
        self.assertEqual(len(strip), 10 + 2*4)
        self.assertAlmostEqual(min(p.length for p in strip), .03/16)
        # one more level per doubling of the density beyond 32 panels per wavelength
        dense = _panels(_snapshot(_segment([(0., 0.), (.3, 0.)], n=40)))
        self.assertAlmostEqual(min(p.length for p in dense), .3/40/32)

    def test_an_impedance_junction_at_a_corner_is_graded_once(self):
        law = ['1', 'constant', '75', '-20', '0', '0']
        square = _square()
        snapshot = _snapshot(_segment(square[:3], n=10, name='pec'), _segment(square[2:], n=10, ibc=1, name='ibc'),
                             ibcs=[law])
        panels = _panels(snapshot)
        # the two junction corners take the junction's four levels, the two plain corners two
        self.assertEqual(len(panels), 40 + 2*2*4 + 2*2*2)

    def test_grading_is_unit_independent(self):
        inches = _snapshot(_segment([(x/.0254, y/.0254) for x, y in _square()], n=-20))
        meters = _snapshot(_segment(_square(), n=-20))
        a, b = _panels(inches, scale=.0254), _panels(meters)
        np.testing.assert_allclose(_geometry(a), _geometry(b), atol=1e-12)

    def test_short_primitives_below_the_singular_depth_are_not_refined(self):
        # a 0.001-inch end face of a plate: its own panel is already below the graded depth
        t = .001*.0254
        plate = _snapshot(_segment([(0., 0.), (0., t), (.0254, t), (.0254, 0.), (0., 0.)]))
        panels = _panels(plate, frequency=40.)
        ends = [p for p in panels if abs(p.tangent[0]) < .5]
        self.assertEqual(len(ends), 2)
        self.assertLessEqual(len(panels) - len(_ungraded(plate, frequency=40.)), 2*2*4)

    def test_the_certification_fine_mesh_keeps_the_grading(self):
        from ghost_backend.runs.quality import scale_snapshot_panel_density
        base = _snapshot(_segment(_rhombus(.1)))
        fine = scale_snapshot_panel_density(base, 1.5)
        fine['_2d_certification_refinement_factor'] = 1.5
        fine['_2d_certification_base_segment_n'] = [0]
        coarse, refined = _panels(base), _panels(fine)
        self.assertGreater(len(refined), len(coarse))
        h = lambda panels: max(p.length for p in panels)
        t = lambda panels: min(p.length for p in panels)
        # the innermost panel shrinks at least as fast as the uniform panels
        self.assertLessEqual(t(refined)/t(coarse), h(refined)/h(coarse) + 1e-9)
        ratios = [b.length/a.length for a, b in zip(refined[:-1], refined[1:])]
        self.assertLessEqual(max(max(ratios), 1/min(ratios)), 2. + 1e-9)

    def test_the_panel_limit_counts_the_graded_panels(self):
        snapshot = _snapshot(_segment(_square(), n=10))
        with self.assertRaisesRegex(ValueError, 'panel limit|limit is'):
            _panels(snapshot, max_panels=45)
        self.assertEqual(len(_panels(snapshot, max_panels=56)), 56)


class GradedAccuracyTests(unittest.TestCase):
    def _rcs(self, snapshot, pol, frequency=1.):
        result = td.solve_monostatic_rcs_2d_single_polarization(snapshot, [frequency], [0., 30., 90.], pol,
                                                                  geometry_units='meters')
        return 10*np.log10([s['rcs_linear'] for s in result['samples']]), result['metadata']['panel_count']

    def test_a_strip_reaches_a_hundredth_of_a_db_with_a_sixth_of_the_panels(self):
        strip = lambda n: _snapshot(_segment([(.15, 0.), (-.15, 0.)], n=n))
        reference, _ = self._rcs(strip(320), 'TM')
        graded, panels = self._rcs(strip(10), 'TM')
        with patch.object(tg, 'SHARP_GRADING_MAX_EXPONENT', 0.):
            uniform, uniform_panels = self._rcs(strip(20), 'TM')
        self.assertLess(np.max(np.abs(graded - reference)), .012)              # 18 panels
        self.assertGreater(np.max(np.abs(uniform - reference)), .03)           # 20 panels, first order
        self.assertLess(panels, uniform_panels)


class BorSharpGradingTests(unittest.TestCase):
    @staticmethod
    def _chain(points, n=10, seg_type=2):
        return dispatch._SegChain('s', seg_type, n, 0, 0, 0, np.asarray(points, dtype=float))

    def test_a_rim_is_graded_like_the_2d_knife_edge_and_counting_matches_meshing(self):
        h = .15*math.tan(math.radians(2.5))
        chain = self._chain([(0., h), (.15, 0.), (0., -h)])
        levels = dispatch._sharp_run_levels([chain], .3)
        self.assertEqual(levels, {(0, 0): (0, 4), (0, 1): (4, 0)})
        points = dispatch._mesh_generatrix([chain], .3, 1000, 1e-12)[0]
        self.assertEqual(len(points) - 1, 20 + 8)
        self.assertEqual(dispatch._run_element_count([chain], .3), len(points) - 1)
        lengths = np.hypot(*np.diff(points, axis=0).T)
        self.assertAlmostEqual(lengths.min()/lengths.max(), 1/16, places=6)

    def test_smooth_generatrices_keep_their_meshes(self):
        sphere = self._chain(bor.sphere_generatrix(.1, 24), n=1)
        self.assertEqual(dispatch._sharp_run_levels([sphere], .3), {})
        self.assertEqual(len(dispatch._mesh_generatrix([sphere], .3, 1000, 1e-12)[0]) - 1, 24)

    def test_axis_tips_take_the_conical_exponent(self):
        tip = lambda deg: dispatch._axis_tip_exponent(math.radians(deg))
        self.assertAlmostEqual(tip(1.), 2*.1052, places=3)       # 2 nu_D, P_nu(-cos theta) = 0
        self.assertAlmostEqual(tip(15.), 2*.2387, places=3)
        self.assertEqual(tip(60.), 1.)
        self.assertEqual(tip(90.), 1.)
        # a 2-degree needle: tip held to four levels, the base rim graded as a 2D corner
        r = .3*math.tan(math.radians(1.))
        needle = self._chain([(0., .15), (r, -.15), (0., -.15)], n=40)
        levels = dispatch._sharp_run_levels([needle], .3)
        self.assertEqual(levels[(0, 0)][0], dispatch.BOR_AXIS_TIP_MAX_LEVELS)
        self.assertGreater(levels[(0, 0)][1], 0)
        self.assertEqual(levels.get((0, 1), (0, 0))[1], 0)                   # the flat base meets the axis smoothly
        points = dispatch._mesh_generatrix([needle], .3, 1000, 1e-12)[0]
        self.assertEqual(dispatch._run_element_count([needle], .3), len(points) - 1)

    def test_the_certification_fine_generatrix_keeps_the_grading(self):
        h = .15*math.tan(math.radians(2.5))
        base = self._chain([(0., h), (.15, 0.), (0., -h)], n=-10)
        fine = dispatch._SegChain('s', 2, -15, 0, 0, 0, base.pts.copy(), certification_base_n=-10,
                                  certification_refinement_factor=1.5)
        coarse = dispatch._mesh_generatrix([base], .3, 1000, 1e-12)[0]
        refined = dispatch._mesh_generatrix([fine], .3, 1000, 1e-12)[0]
        length = lambda points: np.hypot(*np.diff(points, axis=0).T)
        self.assertGreater(len(refined), len(coarse))
        self.assertLessEqual(length(refined).min()/length(coarse).min(),
                             length(refined).max()/length(coarse).max() + 1e-9)

    def test_preview_counts_the_graded_mesh(self):
        h = .15*math.tan(math.radians(2.5))
        snapshot = _snapshot(_segment([(0., h), (.15, 0.), (0., -h)], n=10))
        estimate = dispatch.estimate_bor_resources(snapshot, 1., [0.], geometry_units='meters', workers=1,
                                                   mesh_certification=False, bor_options=dict(factorization='dense'))
        self.assertEqual(estimate['mesh_elements'], 28)


if __name__ == '__main__':
    unittest.main()
