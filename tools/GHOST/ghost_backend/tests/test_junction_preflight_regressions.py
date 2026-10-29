"""Physical invariants for multi-material junctions and submicrometer coatings."""
import copy
import math
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.twod import geometry as g, solver


def segment(name, kind, points, pos=0, neg=0):
    return dict(name=name, seg_type=kind,
                properties=[str(kind), "0", "0", str(pos), str(neg)],
                point_pairs=[dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1])
                             for a, b in zip(points[:-1], points[1:])])


def arc(radius, start, stop, count):
    return [(round(radius * math.cos(t), 14), round(radius * math.sin(t), 14))
            for t in np.linspace(start, stop, count + 1)]


def sectors(count, reverse=()):
    pieces = []
    for i in range(count):
        a, b = 2 * math.pi * i / count, 2 * math.pi * (i + 1) / count
        pieces.append(segment(f"arc{i}", 3, arc(.1, b, a, 48 // count), i + 1))
        points = [(0., 0.), arc(.1, a, a, 1)[0]]
        pos, neg = i + 1, (i - 1) % count + 1
        if i in reverse:
            points.reverse()
            pos, neg = neg, pos
        pieces.append(segment(f"spoke{i}", 5, points, pos, neg))
    return dict(segments=pieces, ibcs=[], dielectrics=[
        [str(i + 1), str(eps), str(-.01 * eps), "1", "0"]
        for i, eps in enumerate((2., 4., 8., 12.)[:count])])


def amplitudes(result):
    return np.array([complex(s["rcs_amp_real"], s["rcs_amp_imag"])
                     for s in result["samples"]])


@pytest.mark.parametrize("count", [3, 4])
@pytest.mark.parametrize("pol", ["TM", "TE"])
def test_monostatic_junction_is_invariant_to_direction_and_material_relabel(count, pol):
    options = dict(geometry_units="meters", strict_quality_gate=False,
                   execution_options=dict(factorization="dense", mesh_strategy="global",
                                          assembly_threads=2, blas_threads=2))
    fields = []
    for reverse in ((), (0,), tuple(range(count))):
        result = solver.solve_monostatic_rcs_2d_single_polarization(
            sectors(count, reverse), [.7], [0., 37.], pol, **options)
        fields.append(amplitudes(result))
        assert result["metadata"]["junction_orientation_conflict_nodes"] == 0
    for field in fields[1:]:
        np.testing.assert_allclose(field, fields[0], rtol=1e-10, atol=1e-12)
    bistatic = solver.solve_bistatic_rcs_2d_single_polarization(
        sectors(count), [.7], [0., 37.], [0., 37.], pol, **options)
    np.testing.assert_allclose(np.diag(amplitudes(bistatic).reshape(2, 2)),
                               fields[0], rtol=1e-10, atol=1e-12)


def test_reversal_without_swapping_material_sides_is_still_rejected():
    shape = sectors(3)
    pair = shape["segments"][1]["point_pairs"][0]
    pair["x1"], pair["x2"] = pair["x2"], pair["x1"]
    pair["y1"], pair["y2"] = pair["y2"], pair["y1"]
    with pytest.raises(ValueError, match="region|orientation"):
        g.validate_geometry_snapshot_for_solver(shape, ".")


def coating(gap, mode, scale):
    start, stop = (0., -2 * math.pi) if mode == "2d" else (math.pi / 2, -math.pi / 2)
    outer = arc(.1 + gap, start, stop, 64)
    inner = arc(.1, start, stop, 64)
    outer = [(x / scale, y / scale) for x, y in outer]
    inner = [(x / scale, y / scale) for x, y in inner]
    return dict(segments=[segment("outer", 3, outer, 1), segment("core", 4, inner, 1)],
                ibcs=[], dielectrics=[["1", "4", "-.1", "1", "0"]])


@pytest.mark.parametrize("gap", [1e-6, 5e-7, 2e-9])
@pytest.mark.parametrize("mode", ["2d", "bor"])
@pytest.mark.parametrize("scale", [1., .0254])
def test_distinct_thin_coating_boundaries_pass_in_both_unit_systems(gap, mode, scale):
    shape = coating(gap, mode, scale)
    result = g.validate_geometry_snapshot_for_solver(shape, ".", meters_scale=scale, mode=mode)
    assert result["primitive_count"] == 128
    if mode == "bor":
        g.check_bor_regions_or_raise(shape["segments"], scale)


@pytest.mark.parametrize("reverse", [False, True])
def test_actual_duplicate_boundary_is_still_rejected(reverse):
    shape = coating(5e-7, "2d", 1.)
    duplicate = copy.deepcopy(shape["segments"][0])
    duplicate["name"] = "duplicate"
    if reverse:
        duplicate["point_pairs"] = [dict(x1=p["x2"], y1=p["y2"], x2=p["x1"], y2=p["y1"])
                                   for p in reversed(duplicate["point_pairs"])]
    shape["segments"].append(duplicate)
    with pytest.raises(ValueError, match="Duplicate primitive"):
        g.validate_geometry_snapshot_for_solver(shape, ".")


def test_earlier_anchors_do_not_merge_boundaries_beyond_the_weld_diameter():
    shape = dict(segments=[
        segment("anchor0", 1, [(0., 0.), (-.01, -.01)]),
        segment("anchor1", 1, [(.1, 0.), (.11, -.01)]),
        segment("upper", 1, [(0., .8e-9), (.1, .8e-9)]),
        segment("lower", 1, [(0., -.8e-9), (.1, -.8e-9)]),
    ], ibcs=[], dielectrics=[])
    # Each endpoint is close to an earlier anchor, but the two boundaries
    # are 1.6 nm apart. A cluster cannot grow beyond the 1 nm weld diameter.
    assert g.validate_geometry_snapshot_for_solver(shape, ".")["primitive_count"] == 4
    mesh = g._build_linear_mesh(g._build_panels(shape, 1., 1.))
    upper = [element for element in mesh.elements if element.name == "upper"]
    lower = [element for element in mesh.elements if element.name == "lower"]
    assert upper[0].node_ids[0] != lower[0].node_ids[0]
    assert upper[-1].node_ids[1] != lower[-1].node_ids[1]


@pytest.mark.parametrize("points, message", [
    ([(-.2, 0.), (.2, 0.)], "intersection"),
    ([(-.1, 0.), (.1, 0.)], "intersection|overlap"),
    ([(.2 + 1e-7, 0.), (.3, 0.)], "Geometry crack"),
])
def test_crossings_partial_overlaps_and_free_end_cracks_are_still_rejected(points, message):
    base = [(0., -.1), (0., .1)] if message == "intersection" else [(0., 0.), (.2, 0.)]
    shape = dict(segments=[segment("first", 1, base), segment("second", 1, points)],
                 ibcs=[], dielectrics=[])
    with pytest.raises(ValueError, match=message):
        g.validate_geometry_snapshot_for_solver(shape, ".")
