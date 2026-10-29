"""Whole-geometry material regions: thin layers, mislabels, gaps and BoR meridians.

Thin layers are 0.001 inch (25.4 um) thick on bodies from 1 to 500 inches,
drawn in inches and in meters. Correct geometries must pass every check
(region check, solver preflight, GUI validation); each mislabel must be
caught and must name the segment that carries the wrong label.
"""
import math
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.geometry.io import Segment
from ghost_backend.geometry.regions import (
    AIR, CONDUCTOR, analyze_regions, dielectric, primitives_from_editor_segments,
    primitives_from_snapshot_segments,
)
from ghost_backend.geometry.validation import GeometryAudit
from ghost_backend.twod import geometry as g

THIN_IN = 0.001
DIELECTRICS = [["1", "4.0", "-0.4", "1.0", "0.0"], ["2", "9.0", "-0.9", "1.0", "0.0"],
               ["3", "2.0", "-0.1", "1.0", "0.0"]]
SIZES_IN = [1.0, 500.0]
UNITS = {"inches": 1.0, "meters": 0.0254}
SCALE_TO_M = {"inches": 0.0254, "meters": 1.0}


def seg(name, points, seg_type, pos=0, neg=0):
    return dict(name=name, seg_type=str(seg_type),
                properties=[str(seg_type), "0", "0", str(pos), str(neg)],
                point_pairs=[dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1])
                             for a, b in zip(points[:-1], points[1:])])


def snapshot(segments):
    return dict(segments=list(segments), ibcs=[], dielectrics=[list(r) for r in DIELECTRICS])


def arc(radius, a0, a1, count, scale=1.0):
    return [(scale * radius * math.cos(a0 + (a1 - a0) * i / count),
             scale * radius * math.sin(a0 + (a1 - a0) * i / count)) for i in range(count + 1)]


def circle(radius, count=64, scale=1.0, cw=True):
    points = arc(radius, 0.0, -2 * math.pi if cw else 2 * math.pi, count, scale)
    points[-1] = points[0]
    return points


def split(points, parts):
    n = len(points) - 1
    cuts = [round(i * n / parts) for i in range(parts + 1)]
    return [points[cuts[i]:cuts[i + 1] + 1] for i in range(parts)]


def report(snap, mode="2d"):
    return analyze_regions(primitives_from_snapshot_segments(snap["segments"], mode=mode), mode=mode)


def preflight(snap, units, mode="2d"):
    with tempfile.TemporaryDirectory() as directory:
        return g.validate_geometry_snapshot_for_solver(
            snap, base_dir=directory, meters_scale=SCALE_TO_M[units], mode=mode)


def editor_segments(snap):
    out = []
    for item in snap["segments"]:
        xs, ys = [], []
        for pair in item["point_pairs"]:
            xs += [pair["x1"], pair["x2"]]
            ys += [pair["y1"], pair["y2"]]
        out.append(Segment(item["name"], item["seg_type"], list(item["properties"]), xs, ys))
    return out


def gui(snap, mode="2d"):
    findings, rows = GeometryAudit(editor_segments(snap), [], DIELECTRICS, ".", mode=mode).run()
    return [m for s, _, m in findings if s == "ERROR"], [m for s, _, m in findings if s == "WARN"], rows


def assert_clean(snap, units, mode="2d"):
    rep = report(snap, mode)
    assert rep.errors() == [], rep.errors()
    assert rep.near_misses == []
    result = preflight(snap, units, mode)
    assert not any("almost meet" in w for w in result["warnings"])
    errors, warns, _ = gui(snap, mode)
    assert errors == [], errors
    assert not any("almost meet" in w for w in warns)
    return rep


def assert_caught(snap, units, culprit, mode="2d"):
    rep = report(snap, mode)
    errors = rep.errors()
    assert errors, "mislabel not caught"
    assert any(f"check '{culprit}'" in e for e in errors), errors
    with pytest.raises(ValueError, match="region|orientation"):
        preflight(snap, units, mode)
    gui_errors, _, rows = gui(snap, mode)
    assert any(culprit in e for e in gui_errors), gui_errors
    names = [s["name"] for s in snap["segments"]]
    assert names.index(culprit) in rows


# ----------------------------------------------------------------- geometries


def coated(size, unit, core_pos=1, outer_pos=1, parts=(1, 1)):
    """Thin TYPE 3 coating over a TYPE 4 core: aligned vertices, so a true offset."""
    s, r = UNITS[unit], size / 2
    outer = circle(r + THIN_IN, 96, s)
    inner = circle(r, 96, s)
    segs = [seg(f"outer{i}" if parts[0] > 1 else "outer", p, 3, outer_pos)
            for i, p in enumerate(split(outer, parts[0]))]
    segs += [seg(f"core{i}" if parts[1] > 1 else "core", p, 4, core_pos)
             for i, p in enumerate(split(inner, parts[1]))]
    return snapshot(segs)


def partial(size, unit, core_pos=1, wall_pos=1):
    """A thin coating over the top half of a PEC disc: two T-junctions."""
    s, r = UNITS[unit], size / 2
    return snapshot([
        seg("shell", arc(r + THIN_IN, math.pi, 0.0, 48, s), 3, 1),
        seg("wall_r", [(s * (r + THIN_IN), 0.0), (s * r, 0.0)], 3, wall_pos),
        seg("core_top", arc(r, math.pi, 0.0, 48, s), 4, core_pos),
        seg("wall_l", [(-s * r, 0.0), (-s * (r + THIN_IN), 0.0)], 3, 1),
        seg("core_bot", arc(r, 2 * math.pi, math.pi, 48, s), 2),
    ])


def nested(size, unit, outer=(1,), mid=(1, 2), core=(2,)):
    """TYPE 3 (d1) / TYPE 5 (d1 over d2) / TYPE 4 (d2) layers 0.001 in apart."""
    s, r = UNITS[unit], size / 2
    return snapshot([seg("outer", circle(r + 2 * THIN_IN, 96, s), 3, *outer),
                     seg("mid", circle(r + THIN_IN, 96, s), 5, *mid),
                     seg("core", circle(r, 96, s), 4, *core)])


def rectangle(x0, y0, x1, y1):
    return [(x0, y0), (x0, y1), (x1, y1), (x1, y0), (x0, y0)]       # CW


def pec_walls(size, unit, closed=True):
    """Two PEC walls 0.001 in apart: thin closed plates, or open plates."""
    s = UNITS[unit]
    if closed:
        h = 0.01 * size
        return snapshot([seg("lower", rectangle(0, -h, s * size, 0), 2),
                         seg("upper", rectangle(0, s * THIN_IN, s * size, s * THIN_IN + h), 2)])
    return snapshot([seg("lower", [(s * size, 0.0), (0.0, 0.0)], 2),
                     seg("upper", [(0.0, s * THIN_IN), (s * size, s * THIN_IN)], 2)])


# ---------------------------------------------------------------------- tests


@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("size", SIZES_IN)
class TestThinLayers:

    def test_closed_thin_coating(self, size, unit):
        rep = assert_clean(coated(size, unit), unit)
        media = sorted(r.medium for r in rep.regions)
        assert media == sorted([AIR, CONDUCTOR, dielectric(1)])
        ring = next(r for r in rep.regions if r.medium == dielectric(1))
        assert len(ring.holes) == 1        # the core is a hole of the 25 um ring, not filled
        assert ring.area == pytest.approx(math.pi * ((size / 2 + THIN_IN) ** 2 - (size / 2) ** 2)
                                          * UNITS[unit] ** 2, rel=0.01)

    def test_thin_coating_split_into_arcs(self, size, unit):
        assert_clean(coated(size, unit, parts=(4, 3)), unit)

    def test_partial_thin_coating_with_t_junctions(self, size, unit):
        assert_clean(partial(size, unit), unit)

    def test_nested_thin_layers(self, size, unit):
        rep = assert_clean(nested(size, unit), unit)
        assert sorted(r.medium for r in rep.regions) == sorted(
            [AIR, dielectric(1), dielectric(2), CONDUCTOR])

    @pytest.mark.parametrize("closed", [True, False])
    def test_parallel_pec_walls(self, size, unit, closed):
        rep = assert_clean(pec_walls(size, unit, closed), unit)
        assert {r.medium for r in rep.regions} == ({AIR, CONDUCTOR} if closed else {AIR})

    def test_mislabeled_closed_coating(self, size, unit):
        assert_caught(coated(size, unit, core_pos=2), unit, "core")

    def test_mislabeled_arc(self, size, unit):
        snap = coated(size, unit, parts=(4, 3))
        snap["segments"][2]["properties"][3] = "2"
        assert_caught(snap, unit, "outer2")
        snap = coated(size, unit, parts=(4, 3))
        snap["segments"][5]["properties"][3] = "2"
        assert_caught(snap, unit, "core1")

    @pytest.mark.parametrize("core_pos, wall_pos, culprit", [(2, 1, "core_top"), (1, 2, "wall_r")])
    def test_mislabeled_partial_coating(self, size, unit, core_pos, wall_pos, culprit):
        assert_caught(partial(size, unit, core_pos, wall_pos), unit, culprit)

    @pytest.mark.parametrize("layers, culprit", [
        (dict(outer=(2,)), "outer"),
        (dict(mid=(2, 1)), "mid"),
        (dict(core=(1,)), "core"),
        (dict(mid=(1, 3)), "mid"),
    ])
    def test_mislabeled_nested_layers(self, size, unit, layers, culprit):
        assert_caught(nested(size, unit, **layers), unit, culprit)


def test_mislabel_names_the_fix():
    rep = report(nested(1.0, "inches", mid=(2, 1)))
    assert "swap its pos_mat and neg_mat" in rep.errors()[0]
    rep = report(partial(1.0, "inches", core_pos=2))
    assert "set pos_mat=1" in rep.errors()[0]


def test_weld_never_merges_points_farther_apart_than_the_tolerance():
    from ghost_backend.geometry.regions import _weld
    tol = 1e-9
    points = [(0.0, 0.0), (0.9e-9, 0.0), (1.8e-9, 0.0), (5.0, 5.0), (5.0 + 2e-10, 5.0)]
    ids, _ = _weld(points, tol)
    assert ids[0] == ids[1] and ids[2] != ids[0]
    assert ids[3] == ids[4]


def test_nearly_parallel_close_edges_sort_exactly():
    # Two edges from one vertex 1e-14 rad apart: the float cross product is
    # below its error bound, the exact fallback still orders them.
    from ghost_backend.geometry.regions import _orient
    o, a = (250.0, 250.0), (750.0, 250.0)
    b = (750.0, 250.0 + 5e-12)
    assert _orient(o, a, b) == 1 and _orient(o, b, a) == -1
    assert _orient(o, a, (1250.0, 250.0)) == 0


# ----------------------------------------------------------------- gaps


def test_dielectric_near_miss_is_located():
    ring = circle(0.5, 64)
    gap = 0.0005
    end = (ring[-2][0] + 0.99 * (ring[-1][0] - ring[-2][0]), ring[-2][1] + 0.99 * (ring[-1][1] - ring[-2][1]))
    snap = snapshot([seg("ring", ring[:-1] + [end], 3, 1)])
    rep = report(snap)
    assert len(rep.near_misses) == 1
    miss = rep.near_misses[0]
    assert miss.gap == pytest.approx(math.dist(end, ring[-1]), rel=1e-6)
    assert "Segments 'ring' and 'ring' almost meet at" in rep.errors()[0]
    with pytest.raises(ValueError, match="Open material boundary.*almost meet"):
        preflight(snap, "inches")
    with pytest.raises(ValueError, match="Open dielectric boundary.*almost meet"):
        g._build_panels(snap, 0.0254, 0.3)
    assert gap


def test_tm_slit_warns_and_te_refusal_names_the_gap():
    from ghost_backend.twod.solver import solve_monostatic_rcs_2d_single_polarization
    ring = circle(0.05, 48)
    end = (ring[-2][0] + 0.98 * (ring[-1][0] - ring[-2][0]), ring[-2][1] + 0.98 * (ring[-1][1] - ring[-2][1]))
    snap = snapshot([seg("pec", ring[:-1] + [end], 2)])
    result = preflight(snap, "meters")
    assert any("Open TYPE 2 boundary" in w and "almost meet" in w for w in result["warnings"])
    _, warns, _ = gui(snap)
    assert any("almost meet" in w for w in warns)
    with pytest.raises(ValueError, match="Open TYPE 2.*almost meet"):
        solve_monostatic_rcs_2d_single_polarization(snap, [1.0], [0.0], "TE", geometry_units="meters")


@pytest.mark.parametrize("unit", UNITS)
def test_intentional_thin_separations_give_no_gap_findings(unit):
    for snap in (coated(500.0, unit), nested(1.0, unit), pec_walls(500.0, unit, closed=True),
                 pec_walls(1.0, unit, closed=False)):
        assert report(snap).near_misses == []


# ------------------------------------------------------------------- BoR


def meridian(radius, count=48, scale=1.0, z0=0.0):
    """Top-to-bottom half circle at x >= 0: the outward-normal BoR traversal."""
    pts = arc(radius, math.pi / 2, -math.pi / 2, count, scale)
    pts = [(abs(x) if abs(x) > 1e-15 else 0.0, y + z0) for x, y in pts]
    pts[0], pts[-1] = (0.0, pts[0][1]), (0.0, pts[-1][1])
    return pts


def bor_cases():
    r = 0.5
    cylinder = [(0.0, 2.0), (1.0, 2.0), (1.0, -2.0), (0.0, -2.0)]
    return {
        "sphere": snapshot([seg("sphere", meridian(r), 2)]),
        "finite_cylinder": snapshot([seg("top", cylinder[:2], 2), seg("wall", cylinder[1:3], 2),
                                     seg("bottom", cylinder[2:], 2)]),
        "dielectric_sphere": snapshot([seg("sphere", meridian(r), 3, 1)]),
        "coated_sphere": snapshot([seg("outer", meridian(r + THIN_IN), 3, 1),
                                   seg("core", meridian(r), 4, 1)]),
        "layered_sphere": snapshot([seg("outer", meridian(r + 2 * THIN_IN), 3, 1),
                                    seg("mid", meridian(r + THIN_IN), 5, 1, 2),
                                    seg("core", meridian(r), 4, 2)]),
    }


@pytest.mark.parametrize("name", list(bor_cases()))
def test_correct_bor_meridians_pass(name):
    snap = bor_cases()[name]
    rep = assert_clean(snap, "inches", "bor")
    assert rep.closure_failures == []
    assert AIR in {r.medium for r in rep.regions}


@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("size", SIZES_IN)
def test_thin_bor_layers_pass_and_swapped_labels_are_caught(size, unit):
    s, r = UNITS[unit], size / 2
    snap = snapshot([seg("outer", meridian(r + 2 * THIN_IN, 96, s), 3, 1),
                     seg("mid", meridian(r + THIN_IN, 96, s), 5, 1, 2),
                     seg("core", meridian(r, 96, s), 4, 2)])
    assert_clean(snap, unit, "bor")
    snap["segments"][1]["properties"][3:5] = ["2", "1"]
    assert any("check 'mid'" in e and "swap its pos_mat and neg_mat" in e
               for e in report(snap, "bor").errors())


def test_bor_partial_coating_regression_snapshot_passes():
    from test_bor_physics_regression import _partial_coating_snapshot
    snap = _partial_coating_snapshot()
    rep = report(snap, "bor")
    assert rep.errors() == []


@pytest.mark.parametrize("name, index, labels, culprit", [
    ("coated_sphere", 1, ("2", "0"), "core"),
    ("layered_sphere", 0, ("2", "0"), "outer"),
    ("layered_sphere", 1, ("2", "1"), "mid"),
    ("dielectric_sphere", 0, None, "sphere"),
])
def test_mislabeled_bor_materials_are_caught(name, index, labels, culprit):
    snap = bor_cases()[name]
    if labels is None:
        # A dielectric meridian drawn bottom-to-top puts the dielectric outside.
        item = snap["segments"][index]
        item["point_pairs"] = [dict(x1=p["x2"], y1=p["y2"], x2=p["x1"], y2=p["y1"])
                               for p in reversed(item["point_pairs"])]
    else:
        snap["segments"][index]["properties"][3:5] = list(labels)
    rep = report(snap, "bor")
    assert any(culprit in e for e in rep.errors()), rep.errors()
    with pytest.raises(ValueError, match=f"(?s)BoR material-region check failed.*'{culprit}'"):
        g.check_bor_regions_or_raise(snap["segments"], 0.0254)
    assert gui(snap, "bor")[0]


def _banded_sphere(wall):
    """PEC sphere, upper half coated with dielectric 1, lower half with 2, TYPE 5 wall between."""
    def quarter(r, a0, a1):
        return [(x if abs(x) > 1e-12 else 0.0, y) for x, y in arc(r, a0, a1, 24)]
    a, b = 0.5, 0.6
    return snapshot([seg("shell_top", quarter(b, math.pi / 2, 0), 3, 1),
                     seg("shell_bot", quarter(b, 0, -math.pi / 2), 3, 2),
                     seg("core_top", quarter(a, math.pi / 2, 0), 4, 1),
                     seg("core_bot", quarter(a, 0, -math.pi / 2), 4, 2),
                     seg("wall", [(a, 0.0), (b, 0.0)], 5, *wall)])


def test_bor_dispatcher_runs_the_region_check_after_its_layout_checks():
    # The banded layout accepted a swapped TYPE 5 wall between two coatings.
    from ghost_backend.bor.dispatch import estimate_bor_resources
    estimate_bor_resources(_banded_sphere((1, 2)), 1.0, [0.0], geometry_units="inches")
    with pytest.raises(ValueError, match="(?s)BoR material-region check failed.*check 'wall'.*swap"):
        estimate_bor_resources(_banded_sphere((2, 1)), 1.0, [0.0], geometry_units="inches")


def test_bor_open_meridian_off_axis_is_an_open_boundary():
    pts = meridian(0.5)[:-3]
    rep = report(snapshot([seg("sphere", pts, 3, 1)]), "bor")
    assert any("Open material boundary" in e for e in rep.errors())


# ------------------------------------------------------------- performance


def test_ten_thousand_primitives_check_quickly():
    import time
    segs = []
    for i in range(50):
        for j in range(50):
            cx, cy = 3.0 * i, 3.0 * j
            segs.append(seg(f"b{i}_{j}", [(cx + x, cy + y) for x, y in circle(1.0, 4)], 3, 1))
    assert sum(len(s["point_pairs"]) for s in segs) == 10000
    prims = primitives_from_snapshot_segments(segs)
    start = time.perf_counter()
    rep = analyze_regions(prims)
    elapsed = time.perf_counter() - start
    assert rep.errors() == []
    assert len(rep.regions) == 2501
    assert elapsed < 1.0, elapsed
