"""Calibration of the far quadrature order of the hypersingular (W) block.

For element pairs at a given centre separation (in units of the longer panel),
electrical length |k|L of the longer panel, loss angle, length ratio and random
orientation, the completed linear-basis Maue block computed by the production
assembly with q points per panel is compared with the same block at 48 points.
The error is the largest entry difference relative to the largest entry of the
converged block (cancellation between the two Maue terms included).

    python w_far_rule.py            # prints the worst error per bin and order
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "tools", "GHOST")))
import numpy as np
import ghost_backend.twod.operators as ops
from ghost_backend.twod.geometry import LinearElement, LinearMesh, LinearNode, _linear_node_snap_key


def element(a, b, index, ids):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    length = float(np.linalg.norm(d))
    t = d / length
    return LinearElement("e%d" % index, 2, 0, 0, 0, tuple(ids), a, b, 0.5 * (a + b), t, np.array([-t[1], t[0]]), length, index)


def pair_mesh(p0, p1, q0, q1):
    nodes = [LinearNode(np.asarray(p, float), _linear_node_snap_key(np.asarray(p, float))) for p in (p0, p1, q0, q1)]
    return LinearMesh(nodes, [element(p0, p1, 0, (0, 1)), element(q0, q1, 1, (2, 3))])


def w_block(mesh, k, order):
    """Far W block of the two-element mesh with exactly ``order`` points per panel.

    Every production order selector is bypassed (the S/K' table, the mesh-wide
    W floor and the per-tile W table), and the rule the assembly really
    requested is recorded and asserted: an earlier version of this helper left
    the per-tile table active, so requests below it were silently raised.
    """
    saved = ops._graded_w_far_floor, ops._graded_far_order, ops._graded_w_far_order, ops._get_quadrature
    used = []

    def recording_quadrature(n, *args, **kwargs):
        used.append(int(n))
        return saved[3](n, *args, **kwargs)

    ops._graded_w_far_floor = lambda *a, **kw: 2
    ops._graded_far_order = lambda kl, ratio, cap, degree=1, attenuating=False: int(cap)
    ops._graded_w_far_order = lambda floor, kl_max, ratio_min, degree: 2
    ops._get_quadrature = recording_quadrature
    try:
        full = np.zeros((4, 4), complex, order="F")
        ops._assemble_linear_hypersingular_matrix(mesh, k, obs_order=order, src_order=order, destination=full)
    finally:
        ops._graded_w_far_floor, ops._graded_far_order, ops._graded_w_far_order, ops._get_quadrature = saved
    block = np.concatenate((full[:2, 2:].ravel(), full[2:, :2].ravel()))
    if not used and not np.any(block):
        # Strongly attenuated pair: production drops the interaction outright
        # (FAR_ATTENUATION_CUT) and integrates nothing.  Not a far-rule cell.
        LAST_RULES[:] = []
        return block
    if int(order) not in used:
        raise AssertionError("requested a {}-point far rule; the assembly used {}".format(order, sorted(set(used))))
    LAST_RULES[:] = sorted(set(used))
    return block


LAST_RULES = []
KL = (1e-4, 1e-2, 0.15, 0.5, 1.0, 1.5, 2.0, 3.0)
ARG = (0.0, -20.0, -45.0, -70.0, -89.9)
RATIO = (1.0, 0.5, 0.1, 0.01, 0.001)
SEPARATION = (3.0, 5.0, 10.0, 30.0)
ORDERS = (5, 6, 7, 8, 9)


def run(samples=10, seed=0, orders=ORDERS):
    rng = np.random.default_rng(seed)
    worst = {}
    special = [(0.0, 0.0), (0.0, math.pi / 2), (math.pi / 2, math.pi / 2), (math.pi / 2, 0.0), (0.3, -0.3)]
    for separation in SEPARATION:
        for kl in KL:
            for arg in ARG:
                for ratio in RATIO:
                    for trial in range(samples):
                        long_len = 1.0
                        short_len = ratio
                        if trial < len(special):
                            a1, a2 = special[trial]  # collinear, perpendicular, parallel broadside, ...
                        else:
                            a1, a2 = rng.uniform(0, 2 * math.pi, 2)
                        swap = trial % 2
                        la, lb = (short_len, long_len) if swap else (long_len, short_len)
                        # A hair beyond the nominal separation: at exactly 3.0 the
                        # rounding of the centre distance left about 6% of the random
                        # orientations just under the far threshold, where no far rule
                        # is used at all (w_block now refuses to measure such a pair).
                        c2 = np.array([separation * (1.0 + 1e-9) * long_len, 0.0])
                        d1 = 0.5 * la * np.array([math.cos(a1), math.sin(a1)])
                        d2 = 0.5 * lb * np.array([math.cos(a2), math.sin(a2)])
                        mesh = pair_mesh(-d1, d1, c2 - d2, c2 + d2)
                        k = (kl / long_len) * complex(math.cos(math.radians(arg)), math.sin(math.radians(arg)))
                        reference = w_block(mesh, k, 48)
                        scale = np.max(np.abs(reference))
                        if not scale:
                            worst["dropped"] = worst.get("dropped", 0) + 1
                            continue
                        worst["measured"] = worst.get("measured", 0) + 1
                        for order in orders:
                            error = float(np.max(np.abs(w_block(mesh, k, order) - reference)) / scale)
                            for key in ((separation, kl, order), ("arg", separation, kl, arg, order), ("ratio", separation, kl, ratio, order)):
                                worst[key] = max(worst.get(key, 0.0), error)
    return worst


if __name__ == "__main__":
    worst = run()
    print("{} cells measured at the requested orders; {} attenuated cells dropped by production and skipped".format(
        worst.get("measured", 0), worst.get("dropped", 0)))
    print("worst completed-block error, linear basis; rows |k|L, columns order " + str(ORDERS))
    for separation in SEPARATION:
        print("separation {:g} panel lengths".format(separation))
        for kl in KL:
            print("  |k|L {:<7g} ".format(kl) + "  ".join("{:.1e}".format(worst[separation, kl, q]) for q in ORDERS))
