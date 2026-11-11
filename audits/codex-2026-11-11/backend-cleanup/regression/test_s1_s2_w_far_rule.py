"""S-1 / S-2: the graded W far rule stays inside its error bound, slivers included."""
import os
import sys
from common import *
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "calibration"))
import ghost_backend.twod.operators as ops
from w_far_rule import element
from ghost_backend.twod.geometry import LinearMesh, LinearNode, _linear_node_snap_key

# --- order selection ------------------------------------------------------------
order = ops._graded_w_far_order
check("typical mesh (|k|L 0.31): 7 / 6 / 5 points by separation", (order(8, 0.31, 3.0, 1), order(8, 0.31, 5.0, 1), order(8, 0.31, 10.0, 1)) == (7, 6, 5))
check("|k|L up to 3 keeps the former 8 points", all(order(8, 3.0, s, 1) == 8 for s in (3.0, 5.0, 50.0)))
check("order never exceeds the former rule", all(order(8, kl, s, 1) <= 8 for kl in (1e-6, 0.1, 0.5, 1.0, 1.5, 2.9) for s in (3.0, 7.0, 40.0)))
check("order is monotone in |k|L and separation",
      all(order(8, a, s, 1) <= order(8, b, s, 1) for a, b in ((0.1, 0.4), (0.4, 0.9), (0.9, 1.4), (1.4, 2.5)) for s in (3.0, 7.0, 40.0))
      and all(order(8, kl, 3.0, 1) >= order(8, kl, 7.0, 1) >= order(8, kl, 40.0, 1) for kl in (0.1, 0.4, 0.9, 1.4, 2.5)))
check("ineligible mesh keeps the 16-point fallback", order(16, 0.3, 10.0, 1) == 16)
check("polynomial degrees keep their 9-point rule", order(9, 0.3, 10.0, 2) == 9 and order(9, 0.3, 10.0, 3) == 9)
lengths = np.r_[np.full(50, 1.0), 5e-4]
check("one sliver no longer forces the fallback", ops._graded_w_far_floor(0.3, lengths, 3.0, 1) == 8)
check("a 1e-7 sliver still does", ops._graded_w_far_floor(0.3, np.r_[lengths, 1e-7], 3.0, 1) == 16)
check("|k|L above 3 still does", ops._graded_w_far_floor(3.5, lengths, 3.0, 1) == 16)
check("active wavenumber still does", ops._graded_w_far_floor(0.3 + 0.1j, lengths, 3.0, 1) == 16)


# --- assembled W against a 48-point far rule ------------------------------------
def ring(count, radius, jitter, seed, sliver=None):
    rng = np.random.RandomState(seed)
    theta = np.linspace(0, 2 * np.pi, count + 1)[:-1]
    theta = -(theta + jitter * (2 * np.pi / count) * rng.uniform(-0.5, 0.5, count))
    theta = list(theta)
    if sliver:
        theta.insert(1, theta[0] + (theta[1] - theta[0]) * sliver)
    pts = [radius * np.array([math.cos(t), math.sin(t)]) for t in theta]
    nodes = [LinearNode(p, _linear_node_snap_key(p)) for p in pts]
    n = len(pts)
    return LinearMesh(nodes, [element(pts[i], pts[(i + 1) % n], i, (i, (i + 1) % n)) for i in range(n)])


def assemble(mesh, k, reference):
    n = len(mesh.nodes)
    out = np.zeros((n, n), complex, order="F")
    saved = ops._graded_w_far_floor, ops._graded_far_order
    if reference:
        ops._graded_w_far_floor = lambda *a, **kw: 2
        ops._graded_far_order = lambda kl, ratio, cap, degree=1, attenuating=False: int(cap)
    try:
        ops._assemble_linear_hypersingular_matrix(mesh, k, obs_order=48 if reference else 8, src_order=48 if reference else 8, destination=out)
    finally:
        ops._graded_w_far_floor, ops._graded_far_order = saved
    return out


worst = 0.0
for label, mesh, kls in (("jittered ring", ring(160, 0.3, 0.6, 4), (0.05, 0.31, 0.9, 1.4, 2.5)),
                         ("ring with a 5e-4 sliver", ring(160, 0.3, 0.3, 5, sliver=5e-4), (0.31, 1.2)),
                         ("ring with a 1e-5 sliver", ring(120, 0.3, 0.3, 6, sliver=1e-5), (0.31,))):
    longest = max(e.length for e in mesh.elements)
    xy = np.array([nd.xy for nd in mesh.nodes])
    far = np.linalg.norm(xy[:, None] - xy[None], axis=2) >= 5.0 * longest   # every contributing pair is a far pair
    for kl in kls:
        for arg in (0.0, -35.0, -80.0):
            k = kl / longest * complex(math.cos(math.radians(arg)), math.sin(math.radians(arg)))
            new, ref = assemble(mesh, k, False), assemble(mesh, k, True)
            error = float(np.max(np.abs(new - ref)[far]) / np.max(np.abs(ref)[far]))
            worst = max(worst, error)
            check("{}: |k|L {:g}, arg k {:g} deg within 1e-12".format(label, kl, arg), error <= 1e-12, "{:.1e}".format(error))
print("worst far-entry error relative to the largest far entry: {:.2e}".format(worst))

# --- end to end: a sliver does not change the answer ----------------------------
from ghost_backend.twod import solver as S
from ghost_backend.validation import cylinder as C
a, n = 0.1, 240
r = radius = a * math.sqrt((2 * math.pi / n) / math.sin(2 * math.pi / n))
theta = list(-np.linspace(0, 2 * np.pi, n + 1))
theta.insert(1, theta[0] + (theta[1] - theta[0]) * 5e-4)
pts = [(r * math.cos(t), r * math.sin(t)) for t in theta]; pts[-1] = pts[0]
g = scene([("b", 2, "2 1 10 0 0", rows(pts))], ibc="10 constant 50 -200 0 0")
out = S.solve_monostatic_rcs_2d(g, [3.0], [0.0], geometry_units="meters", solver_method="direct")
for pol, name in (("VV", "TE"), ("HH", "TM")):
    exact = C.sigma_impedance_cylinder(a, 50 - 200j, 3e9, name)
    d = abs(10 * math.log10(out["samples"][0 if pol == "VV" else 1]["rcs_linear"] / exact))
    check("IBC circle with a sliver matches the series ({})".format(pol), d < 2e-3, "{:.2e} dB".format(d))
finish()
