"""Thin-layer applicability belongs to geometry, not numerical subdivision."""
import copy
from dataclasses import replace

import numpy as np
import pytest

import ghost_backend.twod.solver as rcs
from ghost_backend.twod.formulations.thin_layer import (
    _continuous_oriented_mesh,
    _midsurface_geometry,
    solve_thin_layer_fields,
)


RADIUS = .08
THICKNESS = .001
K0 = 2 * np.pi * 1e9 / rcs.C0


def snapshot(points, count=1):
    return {
        "segments": [dict(name="layer", seg_type=1,
            properties=["1", str(count), "1", "0", "0"],
            point_pairs=[dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1])
                         for a, b in zip(points[:-1], points[1:])])],
        "ibcs": [["1", "thin_dielectric", str(THICKNESS), "2"]],
        "dielectrics": [["2", "3", "-.02", "1", "0"]],
    }


def circle_points():
    theta = np.linspace(0, 2 * np.pi, 81)
    return RADIUS * np.column_stack((np.cos(theta), np.sin(theta)))


def mesh_for(shape):
    materials = rcs.MaterialLibrary.from_entries(shape["ibcs"], shape["dielectrics"], ".")
    panels = rcs._build_panels(shape, 1., rcs.C0 / 1e9)
    infos = rcs._build_coupled_panel_info(panels, materials, 1., "TM", K0)
    return rcs._build_linear_mesh_interface_aware(panels, infos)[0]


@pytest.mark.parametrize("count", [1, 2, 3, 5, 9])
def test_geometric_radius_survives_solver_subdivision(count):
    mesh = mesh_for(snapshot(circle_points(), count))
    # Analytic curvature of this fixed polygonal smooth-curve approximation:
    # exterior turn / chord length. It is intentionally not exactly 1/R.
    expected = THICKNESS * (2 * np.pi / 80) / (2 * RADIUS * np.sin(np.pi / 80))
    _, _, _, evidence = solve_thin_layer_fields(mesh, K0, [0.], "TM", 1, 1, THICKNESS)
    assert evidence["thickness_curvature_ratio"] == pytest.approx(expected, rel=2e-11)
    assert evidence["maximum_geometric_turn_deg"] == pytest.approx(4.5, abs=2e-10)
    assert evidence["smooth_midsurface_assumed"]
    assert not evidence["approximation_error_certified"]


@pytest.mark.parametrize("reverse", [False, True])
def test_collinear_authoring_and_uneven_panel_lengths_preserve_radius(reverse):
    original = snapshot(circle_points())
    fragmented = copy.deepcopy(original)
    fragmented["segments"] = []
    # Uneven collinear authoring subdivisions, separate names and explicit N.
    for edge, pair in enumerate(original["segments"][0]["point_pairs"]):
        a = np.array([pair["x1"], pair["y1"]])
        b = np.array([pair["x2"], pair["y2"]])
        points = a + np.array([0., .17, .71, 1.])[:, None] * (b - a)
        points[0], points[-1] = a, b
        for part in range(3):
            direction = points[part:part + 2]
            if reverse and (edge + part) % 2:
                direction = direction[::-1]
            segment = snapshot(direction, part + 1)["segments"][0]
            segment["name"] = f"edge_{edge}_{part}"
            fragmented["segments"].append(segment)
    fragmented["segments"].reverse()
    expected = _midsurface_geometry(_continuous_oriented_mesh(mesh_for(original)))
    actual = _midsurface_geometry(_continuous_oriented_mesh(mesh_for(fragmented)))
    assert actual == pytest.approx(expected, rel=2e-10)


@pytest.mark.parametrize("count", [1, 3, 4])
def test_certification_refinement_retains_physical_eligibility(count):
    result = rcs.solve_monostatic_rcs_2d_certified(
        snapshot(circle_points(), count), [1.], [0., 37., 90.],
        geometry_units="meters", max_panels=1600,
        execution_options={"assembly_threads": 2, "blas_threads": 2})
    assert result["metadata"]["mesh_convergence_certified"]
    expected = THICKNESS * (2 * np.pi / 80) / (2 * RADIUS * np.sin(np.pi / 80))
    for pol in ("VV", "HH"):
        evidence = result["metadata"]["thin_layer"][pol]
        assert evidence
        for row in evidence:
            assert row["thickness_curvature_ratio"] == pytest.approx(expected, rel=2e-10)


@pytest.mark.parametrize("count", [1, 4, 9])
def test_sharp_corner_is_rejected_even_when_thin_radius_ratio_would_pass(count):
    # Old turn/length check accepts this gently sized right-angle bend with
    # arbitrarily thin material, despite the model assuming a smooth surface.
    mesh = mesh_for(snapshot([[-.01, 0.], [0., 0.], [0., .01]], count))
    with pytest.raises(ValueError, match="sharp/coarsely faceted"):
        solve_thin_layer_fields(mesh, K0, [0.], "TM", 1, 1, 1e-8)


@pytest.mark.parametrize("count", [1, 4])
def test_excessive_thickness_curvature_ratio_still_rejects(count):
    mesh = mesh_for(snapshot(circle_points() / 8, count))
    with pytest.raises(ValueError, match="thickness/curvature"):
        solve_thin_layer_fields(mesh, K0, [0.], "TM", 1, 1, THICKNESS)


def test_disconnected_components_use_local_radius():
    outer = mesh_for(snapshot(circle_points()))
    inner = mesh_for(snapshot(circle_points() / 2))
    offset = len(outer.nodes)
    both = rcs.LinearMesh(outer.nodes + inner.nodes,
        outer.elements + [replace(element, node_ids=tuple(i + offset for i in element.node_ids))
                          for element in inner.elements])
    curvature, turn = _midsurface_geometry(_continuous_oriented_mesh(both))
    expected, _ = _midsurface_geometry(_continuous_oriented_mesh(inner))
    assert curvature == pytest.approx(expected)
    assert turn == pytest.approx(4.5)


def test_straight_authored_subdivisions_have_zero_curvature():
    points = np.column_stack((np.linspace(-.05, .05, 41), np.zeros(41)))
    curvature, turn = _midsurface_geometry(_continuous_oriented_mesh(mesh_for(snapshot(points, 3))))
    assert (curvature, turn) == (0., 0.)
