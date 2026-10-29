"""Local proximity pruning must preserve cracks and cancellation semantics."""
import math
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.geometry.spatial import point_proximity_pairs
from ghost_backend.geometry import spatial
from ghost_backend.twod import geometry


@pytest.mark.parametrize("scale, offset", [
    (1., 0.), (1.e-9, 0.), (1.e-3, 1.e6), (1.e-3, -1.e6),
])
def test_local_candidates_preserve_brute_force_distance_pairs(scale, offset):
    rng = np.random.default_rng(3927)
    points = offset + scale * rng.uniform(-2., 2., (160, 2))
    radii = scale * np.exp(rng.uniform(-8., 1., len(points)))
    # Explicit threshold and identical-position cases supplement random input.
    points[:4] = offset + scale * np.array([[0., 0.], [1., 0.], [0., 0.], [1., 1.]])
    radii[:4] = scale
    expected = {(i, j) for i in range(len(points)) for j in range(i+1, len(points))
                if math.dist(points[i], points[j]) <= min(radii[i], radii[j])}
    candidates = list(point_proximity_pairs(iter(points), iter(radii)))
    assert len(candidates) == len(set(candidates))
    actual = {(i, j) for i, j in candidates
              if math.dist(points[i], points[j]) <= min(radii[i], radii[j])}
    assert actual == expected


def strip_shape(count):
    return dict(segments=[
        dict(name=f"strip{i}", properties=["1", "1", "0", "0", "0"],
             point_pairs=[dict(x1=0., y1=2.e-9*i, x2=2.e-9, y2=2.e-9*i)])
        for i in range(count)], ibcs=[], dielectrics=[])


def test_valid_tiny_features_do_not_generate_global_proximity_pairs(monkeypatch):
    candidates = []
    def counted(points, radii, checkpoint=None):
        for pair in point_proximity_pairs(points, radii, checkpoint):
            candidates.append(pair)
            yield pair
    monkeypatch.setattr(spatial, "point_proximity_pairs", counted)
    report = geometry.validate_geometry_snapshot_for_solver(strip_shape(500), ".", 1.)
    assert report["primitive_count"] == 500
    assert report["dangling_nodes"] == 1000
    assert candidates == []


def test_solver_endpoint_proximity_can_be_cancelled(monkeypatch):
    inside_search = [False]
    def checkpoint():
        if inside_search[0]:
            raise InterruptedError("cancel endpoint search")
    def entered(points, radii, checkpoint=None):
        inside_search[0] = True
        yield from point_proximity_pairs(points, radii, checkpoint)
    monkeypatch.setattr(spatial, "point_proximity_pairs", entered)
    with pytest.raises(InterruptedError, match="cancel endpoint search"):
        geometry.validate_geometry_snapshot_for_solver(strip_shape(20), ".", 1.,
                                                       checkpoint=checkpoint)


def test_candidate_build_honors_cancellation_before_finishing():
    visited = []
    def points():
        for i in range(10000):
            visited.append(i)
            yield (float(i), 0.)
    calls = []
    def checkpoint():
        calls.append(None)
        if len(calls) == 3:
            raise InterruptedError("cancel bounds")
    with pytest.raises(InterruptedError, match="cancel bounds"):
        list(point_proximity_pairs(points(), [1.]*10000, checkpoint))
    assert len(visited) < 10000


@pytest.mark.parametrize("scale", [1., .0254])
def test_actual_free_end_crack_is_still_rejected(scale):
    def segment(name, start, end):
        return dict(name=name, properties=["1", "1", "0", "0", "0"],
                    point_pairs=[dict(x1=start/scale, y1=0.,
                                      x2=end/scale, y2=0.)])
    shape = dict(segments=[segment("left", 0., .2),
                           segment("right", .2+1.e-7, .3)],
                 ibcs=[], dielectrics=[])
    with pytest.raises(ValueError, match="Geometry crack"):
        geometry.validate_geometry_snapshot_for_solver(shape, ".", scale)
