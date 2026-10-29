"""Spatial pruning must preserve exact near routing and radius-weighted gaps."""
import math
from pathlib import Path
import sys
from unittest import mock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.bor import solver as bor


def profile(kind, n=80):
    if kind == "sphere":
        return bor.sphere_generatrix(.2, n)
    if kind == "long_first":
        z = np.r_[0., np.linspace(.8, 1., n)]
    elif kind == "long_last":
        z = np.r_[np.linspace(0., .2, n), 1.]
    elif kind == "graded":
        lengths = np.geomspace(1e-4, 1., n)
        z = np.r_[0., np.cumsum(lengths) / np.sum(lengths)]
    else:
        z = np.linspace(0., 1., n + 1)
    rho = .1 + .08 * np.cos(4 * np.pi * z) if kind == "variable_radius" else np.full(n + 1, .1)
    return np.column_stack((rho, z))


@pytest.mark.parametrize("kind", ["sphere", "long_first", "long_last", "graded", "variable_radius"])
@pytest.mark.parametrize("n", [80, 100])
def test_pruned_routing_and_far_gap_match_all_pairs(kind, n):
    obj = bor.BorPecSolver(profile(kind, n), 1e8)
    gen = obj.gen
    expected = [set(range(max(0, e - obj.near_span), min(gen.n_elems, e + obj.near_span + 1)))
                for e in range(gen.n_elems)]
    rho = np.maximum(gen.nodes[gen.elem_n0, 0], gen.nodes[gen.elem_n1, 0])
    direct_scale = 1.001 * 8. * 2. * math.pi / bor.N_XI_SAFETY_CAP
    far_gap = math.inf
    for e in range(gen.n_elems):
        for f in range(e + obj.near_span + 1, gen.n_elems):
            gap = bor._segment_distance(gen.nodes[gen.elem_n0[e]], gen.nodes[gen.elem_n1[e]],
                                        gen.nodes[gen.elem_n0[f]], gen.nodes[gen.elem_n1[f]])
            threshold = max(direct_scale * max(rho[e], rho[f]),
                            2 * max(gen.lengths[e], gen.lengths[f]))
            if gap <= threshold:
                expected[e].add(f)
                expected[f].add(e)
            else:
                far_gap = min(far_gap, gap * np.max(rho) / max(rho[e], rho[f]))
    assert obj._near_sources_by_element == tuple(tuple(sorted(row)) for row in expected)
    assert obj._far_gap() == pytest.approx(0. if math.isinf(far_gap) else far_gap,
                                         rel=1e-12, abs=1e-14)


def test_one_long_panel_does_not_make_short_panel_searches_quadratic():
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

    with mock.patch.object(bor, "cKDTree", CountedTree):
        obj = bor.BorPecSolver(profile("long_first", 800), 1e8)
    # Count candidates, not elapsed time: the previous global-largest radius
    # visited O(N^2) points despite this geometry's linear near-pair count.
    assert visited < 100 * obj.gen.n_elems


@pytest.mark.parametrize("stage", ["near", "far"])
def test_preparation_checks_cancellation(stage):
    obj = bor.BorPecSolver(profile("graded"), 1e8)

    def abort():
        raise InterruptedError("cancel planning")

    obj._checkpoint = abort
    obj._far_gap_cache = None
    with pytest.raises(InterruptedError, match="cancel planning"):
        obj._configure_near_pair_routing() if stage == "near" else obj._far_gap()
