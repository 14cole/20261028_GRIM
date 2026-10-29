"""BoR endpoint topology, regional descriptor safety and bounded validation."""
from pathlib import Path
import sys
import threading
from unittest import mock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.bor import solver as bor, dispatch


def banded(gap=20e-9):
    outer, core = bor.sphere_generatrix(1.+gap, 8), bor.sphere_generatrix(1., 8)
    outer[4, 1] = core[4, 1] = 0.
    surfaces = [(outer[:5], False), (outer[4:], False),
                (np.array([[1., 0.], [1.+gap, 0.]]), False),
                (core[:5], True), (core[4:], True)]
    regions = [dict(medium=None, exterior=True, bounds=[(0, 1), (1, 1)]),
               dict(medium=(3.-.1j, 1.), bounds=[(0, -1), (2, 1), (3, 1)]),
               dict(medium=(4.-.1j, 1.), bounds=[(1, -1), (2, -1), (4, 1)])]
    return surfaces, regions


@pytest.mark.parametrize('gap', [2e-9, 10e-9, 20e-9, 40e-9])
@pytest.mark.parametrize('order', [range(5), [4, 3, 2, 1, 0]])
def test_distinct_thin_band_junctions_stay_separate(gap, order):
    surfaces, regions = banded(gap)
    inverse = {old: new for new, old in enumerate(order)}
    system = bor._MultiRegionBor([surfaces[i] for i in order],
        [dict(r, bounds=[(inverse[i], sign) for i, sign in r['bounds']]) for r in regions], 4e7)
    assert sorted(len(j) for j in system.junctions) == [3, 3]
    assert system.build_Q(0).shape[1] > 0


def segment(name, kind, points, pos=0, neg=0):
    return dict(name=name, seg_type=kind, properties=[str(kind), '1', '0', str(pos), str(neg)],
        point_pairs=[dict(x1=float(a[0]), y1=float(a[1]), x2=float(b[0]), y2=float(b[1]))
                     for a, b in zip(points[:-1], points[1:])])


def test_production_dispatch_preserves_the_two_thin_band_junctions():
    surfaces, _ = banded()
    shape = dict(segments=[segment(str(i), kind, surfaces[i][0], pos, neg)
                 for i, kind, pos, neg in [(0,3,1,0),(1,3,2,0),(2,5,1,2),(3,4,1,0),(4,4,2,0)]],
                 dielectrics=[['1','3','-.1','1','0'],['2','4','-.1','1','0']], ibcs=[])
    class StopAfterTopology(Exception):
        pass
    def inspect(system, *args, **kwargs):
        assert sorted(len(j) for j in system.junctions) == [3, 3]
        raise StopAfterTopology()
    # A condition guard may still reject this extremely thin banded solve;
    # this regression isolates production input -> topology before assembly.
    with mock.patch.object(bor, '_solve_multiregion', side_effect=inspect):
        with pytest.raises(StopAfterTopology):
            dispatch.solve_monostatic_rcs_bor(shape, [.04], [0., 90.], geometry_units='meters',
                max_elements=1000, workers=2, bor_options={'factorization': 'dense'})


@pytest.mark.parametrize('radius', [20e-9, .5e-6, 2e-6])
@pytest.mark.parametrize('scale', [1., .0254])
def test_positive_annular_sheet_radius_survives_axis_classification(radius, scale):
    points = np.array([[radius, 0.], [1., 0.]]) / scale
    shape = dict(segments=[segment('annulus', 1, points)])
    chains = dispatch._chains_from_snapshot(shape, scale)
    groups, tol, axis_tol = dispatch._prepare_bor_groups(chains, 'sheet')
    mesh, _, _ = dispatch._mesh_generatrix(groups[0], 1., 1000, axis_tol)
    assert mesh[0, 0] == pytest.approx(radius, rel=1e-15, abs=0.)
    assert tol == bor.BOR_ENDPOINT_WELD_TOLERANCE_M
    # An older caller passing the former drawing tolerance cannot erase it.
    mesh, _, _ = dispatch._mesh_generatrix(groups[0], 1., 1000, 1e-6)
    assert mesh[0, 0] == pytest.approx(radius, rel=1e-15, abs=0.)


def test_stitch_uses_distance_instead_of_rounded_coordinate_identity():
    a = dispatch._SegChain('first', 1, 1, 0, 0, 0, np.array([[.1,1.],[.1,.49e-9]]))
    b = dispatch._SegChain('second', 1, 1, 0, 0, 0, np.array([[.1,.51e-9],[.1,-1.]]))
    assert dispatch._stitch_generatrix([b,a], 'test', 1e-9) == [a,b]
    assert dispatch._stitch_pieces([b,a], 'test', 1e-9) == [[a,b]]


def valid_regions():
    return [dict(medium=None, exterior=True, bounds=[(0, 1)]),
            dict(medium=(3.-.1j, 1.), bounds=[(0, -1)])]


@pytest.mark.parametrize('change, message', [
    (lambda r: r[1].update(bounds=[(0, 1)]), 'opposite signs'),
    (lambda r: r[1].update(bounds=[(0, -1), (0, -1)]), 'repeats boundary'),
    (lambda r: r.append(dict(medium=(4.,1.),bounds=[(0,-1)])), 'exactly two'),
    (lambda r: r[1].update(bounds=[(0, 0)]), 'sign must'),
    (lambda r: r[1].update(bounds=[(0, -.5)]), 'sign must'),
    (lambda r: r[1].update(bounds=[(0, float('nan'))]), 'sign must'),
    (lambda r: r[1].update(bounds=[(2, -1)]), 'surface index'),
    (lambda r: r[1].update(bounds=[(-1, -1)]), 'surface index'),
    (lambda r: r[1].update(bounds=[]), 'nonempty'),
    (lambda r: r[1].update(exterior=True), 'exterior'),
    (lambda r: r[0].update(exterior=False), 'exactly one'),
    (lambda r: r[0].update(medium=(2.,1.)), 'exterior medium'),
])
def test_invalid_region_descriptors_fail_before_operator_preparation(change, message):
    regions = valid_regions()
    change(regions)
    with mock.patch.object(bor, '_prepared_surface', side_effect=AssertionError('prepared too early')):
        with pytest.raises(ValueError, match=message):
            bor.solve_bor_banded_multiregion([(bor.sphere_generatrix(.06, 8), False)], regions,
                1e9, [0.], workers=2, bor_options={'factorization': 'dense'})


def test_conductor_cannot_have_two_region_incidences():
    with pytest.raises(ValueError, match='conductor surface.*exactly one'):
        bor._MultiRegionBor([(bor.sphere_generatrix(.06, 8), True)], valid_regions(), 1e9)


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('points', [
    [[1.,0.],[1.,4.],[3.,4.],[3.,2.],[.5,2.]],
    [[1.,0.],[1.,4.],[2.,4.],[1.,3.],[1.,1.]],
])
def test_local_owner_validation_rejects_crossing_or_overlap(points, reverse):
    points = np.asarray(points)
    if reverse:
        points = points[::-1]
    with pytest.raises(ValueError, match='intersection/overlap'):
        bor._validate_solve_bor_generatrix(points, 'efie')


def test_graded_validation_has_bounded_candidates_and_checks_cancellation():
    n = 800
    points = np.column_stack((np.full(n+1, .1), np.r_[0.,np.linspace(.8,1.,n)]))
    original = bor.cKDTree
    visited = 0
    class CountedTree:
        def __init__(self, points):
            self.tree = original(points)
        def query_ball_point(self, *args, **kwargs):
            nonlocal visited
            result = self.tree.query_ball_point(*args, **kwargs)
            visited += len(result)
            return result
    with mock.patch.object(bor, 'cKDTree', CountedTree):
        np.testing.assert_array_equal(bor._validate_solve_bor_generatrix(points, 'efie'), points)
    assert visited < 8*n
    def abort():
        raise InterruptedError('cancel validation')
    with mock.patch.object(bor, 'current_checkpoint', return_value=abort):
        with pytest.raises(InterruptedError, match='cancel validation'):
            bor._validate_solve_bor_generatrix(points, 'efie')


def test_public_validation_candidates_include_all_brute_force_contacts():
    rng = np.random.default_rng(90210)
    predicate = bor._segments_intersect_2d
    for _ in range(12):
        points = rng.uniform([.1, -.5], [1., .5], (24, 2))
        tol = max(1e-14, 1e-10 * float(np.ptp(points, axis=0).max()))
        expected = {(i, j) for i in range(len(points)-1) for j in range(i+2, len(points)-1)
                    if predicate(points[i], points[i+1], points[j], points[j+1], tol)}
        indices = {tuple(p): i for i, p in enumerate(points)}
        checked = set()
        def record(a, b, c, d, tolerance):
            checked.add(tuple(sorted((indices[tuple(a)], indices[tuple(c)]))))
            return False  # inspect every contact, rather than stopping at the first
        with mock.patch.object(bor, '_segments_intersect_2d', side_effect=record), \
             mock.patch('ghost_backend.bor.geometry.require_resolved_corners'):
            bor._validate_solve_bor_generatrix(points, 'efie')
        assert expected <= checked


def test_dispatch_cancellation_precedes_geometry_preparation():
    event = threading.Event()
    event.set()
    shape = dict(segments=[segment('sheet', 1, np.array([[.1,0.],[.3,0.]]))],
                 dielectrics=[], ibcs=[])
    with mock.patch.object(dispatch, 'prepare_geometry', side_effect=AssertionError('prepared too early')):
        with pytest.raises(InterruptedError, match='canceled'):
            dispatch.solve_monostatic_rcs_bor(shape, [1.], [0.], geometry_units='meters',
                                             abort_event=event, workers=2,
                                             bor_options={'factorization':'dense'})
