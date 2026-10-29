"""Physical topology and bounded preflight work at coordinate/scale extremes."""
import builtins
import math
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.geometry import regions
from ghost_backend.geometry.io import _chain_area2
from ghost_backend.twod import geometry as g, solver


def segment(name, points, kind=1, ibc=0):
    return dict(name=name, seg_type=kind,
                properties=[str(kind), "1", str(ibc), "0", "0"],
                point_pairs=[dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1])
                             for a, b in zip(points[:-1], points[1:])])


def snapshot(segments, ibcs=()):
    return dict(segments=segments, ibcs=list(ibcs), dielectrics=[])


@pytest.mark.parametrize("shift", [0., .25e-9, .51e-9, 1.e-9])
@pytest.mark.parametrize("scale", [1., .0254])
def test_real_short_element_does_not_collapse_in_a_rounded_cell(shift, scale):
    points = [(shift - .49e-9, shift - .49e-9),
              (shift + .49e-9, shift + .49e-9)]
    shape = snapshot([segment("short", [(x / scale, y / scale) for x, y in points])])
    assert g.validate_geometry_snapshot_for_solver(shape, ".", scale)["dangling_nodes"] == 2
    mesh = g._build_linear_mesh(g._build_panels(shape, scale, 1.))
    assert len(mesh.nodes) == 2
    assert mesh.elements[0].node_ids[0] != mesh.elements[0].node_ids[1]


def test_weld_clusters_have_bounded_diameter_and_exact_repeat_identity():
    points = [(0., 0.), (.9e-9, 0.), (1.8e-9, 0.), (2.7e-9, 0.)]
    welder = regions.PointWelder(1.e-9)
    keys = [welder.key(point) for point in points]
    assert keys == [0, 0, 1, 1]
    assert [welder.key(point) for point in reversed(points)] == keys[::-1]
    for key in set(keys):
        members = [point for point, cluster in zip(points, keys) if cluster == key]
        assert max(math.dist(a, b) for a in members for b in members) <= 1.e-9
    before = len(welder.points)
    assert welder.lookup((.2e-9, 0.)) == 0
    assert welder.lookup((5.e-9, 0.)) is None
    assert len(welder.points) == before
    mesh_welder = g._NodeWelder()
    mesh_keys = [mesh_welder.key(point) for point in points]
    assert [[key == other for other in mesh_keys] for key in mesh_keys] == [
        [key == other for other in keys] for key in keys]


@pytest.mark.parametrize("interface_aware", [False, True])
def test_mesh_builders_reject_an_element_collapsed_by_welding(interface_aware):
    shape = snapshot([segment("short", [(0., 0.), (2.e-9, 0.)], kind=2)])
    panels = g._build_panels(shape, 1., 1.)
    panels[0].p1 = panels[0].p0 + np.array([.5e-9, 0.])
    if interface_aware:
        materials = g.MaterialLibrary.from_entries([], [], ".")
        infos = g._build_coupled_panel_info(panels, materials, .1, "TM", 1.)
        build = lambda: g._build_linear_mesh_interface_aware(panels, infos)
    else:
        build = lambda: g._build_linear_mesh(panels)
    with pytest.raises(ValueError, match="collapses to one mesh node"):
        build()


def test_tiny_sheet_translation_preserves_the_actual_te_response():
    fields = []
    for shift in (0., .25e-9):
        shape = snapshot([segment("short", [(shift - .49e-9, shift - .49e-9),
                                              (shift + .49e-9, shift + .49e-9)], ibc=1)],
                         [["1", "constant", "75", "-20", "0", "0"]])
        result = solver.solve_monostatic_rcs_2d_single_polarization(
            shape, [.1], [0.], "TE", geometry_units="meters",
            execution_options=dict(factorization="dense", mesh_strategy="global",
                                   assembly_threads=2, blas_threads=2))
        assert result["metadata"]["linear_node_count"] == 2
        fields.append(complex(result["samples"][0]["rcs_amp_real"],
                              result["samples"][0]["rcs_amp_imag"]))
    # With one linear element the two physical sheet-end constraints leave
    # zero degrees of freedom. The test guards translation-dependent topology,
    # not an assertion that this coarse field is an accurate nanostrip model.
    assert fields == [0.j, 0.j]


def near_miss_input():
    shape = snapshot([segment("long", [(0., 0.), (1., 0.)], kind=2),
                      segment("target", [(1.02, -.01), (1.02, .01)])] + [
        segment("small" + str(i), [(2. + i, 2.), (2. + i + 1.e-6, 2.)])
        for i in range(4)])
    prims = regions.primitives_from_snapshot_segments(shape["segments"])
    verts = [point for primitive in prims for point in (primitive.start, primitive.end)]
    edges = [(2 * i, 2 * i + 1, i) for i in range(len(prims))]
    return list(range(len(verts))), verts, edges, None, prims, (2,)


def test_mixed_scale_near_miss_search_bounds_empty_cell_work(monkeypatch):
    def bounded_range(*args):
        result = builtins.range(*args)
        assert len(result) <= 4096, "unbounded empty-grid traversal"
        return result
    monkeypatch.setattr(regions, "range", bounded_range, raising=False)
    misses = regions._near_misses(*near_miss_input())
    assert len(misses) == 1
    assert (misses[0].name, misses[0].other_name) == ("long", "target")
    assert misses[0].gap == pytest.approx(.02)


def test_near_miss_fallback_honors_cancellation():
    calls = []
    def checkpoint():
        calls.append(None)
        if len(calls) == 3:
            raise InterruptedError("audit cancellation")
    with pytest.raises(InterruptedError, match="audit cancellation"):
        regions._near_misses(*near_miss_input(), checkpoint=checkpoint)


@pytest.mark.parametrize("scale", [1., .0254])
@pytest.mark.parametrize("radius, offset, dx", [(.001, 1.e6, .123), (.01, 1.e7, .456)])
def test_import_coordinate_offset_does_not_reverse_winding(scale, radius, offset, dx):
    points = [((offset + dx + radius * math.cos(t)) / scale,
               (offset + radius * math.sin(t)) / scale)
              for t in np.linspace(0., -2 * math.pi, 33)]
    points[-1] = points[0]
    assert _chain_area2(points) < 0.
    expected = -32 * radius ** 2 * math.sin(2 * math.pi / 32) / scale ** 2
    assert _chain_area2(points) == pytest.approx(expected, rel=1.e-5)
    shape = snapshot([segment("circle", points, kind=2)])
    assert g.validate_geometry_snapshot_for_solver(shape, ".", scale)["warning_count"] == 0
