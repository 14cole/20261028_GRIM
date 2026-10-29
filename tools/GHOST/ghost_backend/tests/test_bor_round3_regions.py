"""Numerical-axis and spatial-incidence regressions from the third audit."""
from pathlib import Path
import sys
from unittest import mock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.bor import dispatch, solver as bor
from ghost_backend.geometry import regions as geometry_regions
from ghost_backend.geometry.io import Segment
from ghost_backend.geometry.validation import GeometryAudit
from ghost_backend.twod.geometry import check_bor_regions_or_raise


def segment(name, kind, points, pos=0, neg=0):
    return dict(name=name, seg_type=kind,
                properties=[str(kind), "1", "0", str(pos), str(neg)],
                point_pairs=[dict(x1=float(a[0]), y1=float(a[1]),
                                  x2=float(b[0]), y2=float(b[1]))
                             for a, b in zip(points[:-1], points[1:])])


def needle_shape(scale=1.0):
    outer = bor.sphere_generatrix(1.0, 32) * [3e-5, 1.] / scale
    core = bor.sphere_generatrix(.6, 32) * [3e-5, 1.] / scale
    return dict(segments=[segment("outer", 3, outer, 1), segment("core", 4, core, 1)],
                dielectrics=[["1", "3", "-.1", "1", "0"]], ibcs=[])


@pytest.mark.parametrize("scale, units", [(1., "meters"), (.0254, "inches")])
def test_slender_coating_has_same_regions_in_preview_and_solve(scale, units):
    shape = needle_shape(scale)
    check_bor_regions_or_raise(shape["segments"], scale)
    primitives = geometry_regions.primitives_from_snapshot_segments(shape["segments"], mode="bor")
    report = geometry_regions.analyze_regions(
        primitives, mode="bor", tol=1e-9 / scale, meters_scale=scale)
    assert not report.errors()
    assert len(report.regions) == 3
    dispatch.estimate_bor_resources(shape, .04, [0., 90.], geometry_units=units,
                                   workers=2, max_elements=1000,
                                   bor_options={"factorization": "dense"})
    class ReachedOperator(Exception):
        pass
    # This is an input-topology regression, not a condition-number claim for
    # an extremely slender coated body.
    with mock.patch.object(dispatch, "solve_bor_coated_pec", side_effect=ReachedOperator):
        with pytest.raises(ReachedOperator):
            dispatch.solve_monostatic_rcs_bor(
                shape, [.04], [0., 90.], geometry_units=units, workers=2,
                max_elements=1000, bor_options={"factorization": "dense"})


@pytest.mark.parametrize("scale", [1., .0254])
def test_gui_audit_uses_the_same_physical_axis_rule(scale):
    shape = needle_shape(scale)
    segments = []
    for source in shape["segments"]:
        pairs = source["point_pairs"]
        segments.append(Segment(name=source["name"], seg_type=source["seg_type"],
                                properties=source["properties"],
                                x=[q[k] for q in pairs for k in ("x1", "x2")],
                                y=[q[k] for q in pairs for k in ("y1", "y2")]))
    audit = GeometryAudit(segments, [], shape["dielectrics"], ".", mode="bor", meters_scale=scale)
    findings, _ = audit.run()
    assert not [message for severity, _, message in findings if severity == "ERROR"]


@pytest.mark.parametrize("scale", [1., .0254])
def test_axis_threshold_is_physical_and_independent_of_axial_translation(scale):
    for shift in (0., 1e6):
        points = np.array([[.5e-12, shift], [2e-12, shift + 1.], [.1, shift + 2.]]) / scale
        tol = geometry_regions.numerical_bor_axis_tolerance(points, scale)
        assert tol == pytest.approx(1e-12 / scale)
        assert points[0, 0] <= tol < points[1, 0]


def nested(cavity=False):
    surfaces = [(bor.sphere_generatrix(.06, 16), False),
                (bor.sphere_generatrix(.04, 16), False)]
    regions = [dict(medium=None, exterior=True, bounds=[(0, 1)]),
               dict(medium=(3.-.1j, 1.), bounds=[(0, -1), (1, 1)]),
               dict(medium=None if cavity else (6.-.2j, 1.), bounds=[(1, -1)])]
    return surfaces, regions


@pytest.mark.parametrize("conductor", [False, True])
@pytest.mark.parametrize("reverse_order", [False, True])
def test_nested_surfaces_cannot_both_claim_exterior(conductor, reverse_order):
    surfaces, _ = nested()
    surfaces[1] = (surfaces[1][0], conductor)
    if reverse_order:
        surfaces.reverse()
    regions = [dict(medium=None, exterior=True, bounds=[(0, 1), (1, 1)])]
    for si, (_, is_conductor) in enumerate(surfaces):
        if not is_conductor:
            regions.append(dict(medium=(3.-.1j, 1.), bounds=[(si, -1)]))
    with mock.patch.object(bor, "_prepared_surface", side_effect=AssertionError("prepared too early")):
        with pytest.raises(ValueError, match="geometric material regions"):
            bor.solve_bor_banded_multiregion(
                surfaces, regions, 1e9, [0., 90.], workers=2,
                bor_options={"factorization": "dense"})


@pytest.mark.parametrize("cavity", [False, True])
def test_nested_material_and_air_cavity_descriptors_remain_valid(cavity):
    surfaces, regions = nested(cavity)
    system = bor._MultiRegionBor(surfaces, regions, 1e9)
    assert system.n_surf == 2
    assert system.ext_region == 0


def test_disjoint_bodies_share_exterior_and_internal_wall_reversal_stays_valid():
    surfaces, _ = nested()
    surfaces[1] = (surfaces[1][0] + [0., .2], False)
    regions = [dict(medium=None, exterior=True, bounds=[(0, 1), (1, 1)]),
               dict(medium=(3.-.1j, 1.), bounds=[(0, -1)]),
               dict(medium=(6.-.2j, 1.), bounds=[(1, -1)])]
    assert bor._MultiRegionBor(surfaces, regions, 1e9).n_surf == 2

    outer = bor.sphere_generatrix(.06, 16)
    outer[8, 1] = 0.
    wall = np.column_stack((np.linspace(0., .06, 5), np.zeros(5)))
    surfaces = [(outer[:9], False), (outer[8:], False), (wall, False)]
    regions = [dict(medium=None, exterior=True, bounds=[(0, 1), (1, 1)]),
               dict(medium=(3.-.1j, 1.), bounds=[(0, -1), (2, 1)]),
               dict(medium=(6.-.2j, 1.), bounds=[(1, -1), (2, -1)])]
    original = bor._MultiRegionBor(surfaces, regions, 1e9)
    surfaces[2] = (wall[::-1], False)
    regions = [dict(r, bounds=[(i, -sign if i == 2 else sign) for i, sign in r["bounds"]])
               for r in regions]
    reversed_wall = bor._MultiRegionBor(surfaces, regions, 1e9)
    assert len(original.junctions) == len(reversed_wall.junctions) == 1


def test_wrong_surrounding_region_is_rejected_even_when_exterior_is_correct():
    surfaces = [(bor.sphere_generatrix(r, 16), False) for r in (.06, .04, .02)]
    regions = [dict(medium=None, exterior=True, bounds=[(0, 1)]),
               dict(medium=(3.-.1j, 1.), bounds=[(0, -1), (1, 1), (2, 1)]),
               dict(medium=(6.-.2j, 1.), bounds=[(1, -1)]),
               dict(medium=(8.-.2j, 1.), bounds=[(2, -1)])]
    with pytest.raises(ValueError, match="geometric material regions"):
        bor._MultiRegionBor(surfaces, regions, 1e9)

