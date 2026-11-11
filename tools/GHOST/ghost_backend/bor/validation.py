"""Direct BoR solver geometry and aspect-grid validation."""
import numpy as np
from scipy.spatial import cKDTree
from ghost_backend.geometry.regions import numerical_bor_axis_tolerance
from ghost_backend.bor.options import current_checkpoint


def _bor_axis_tolerance(points):
    """Numerical zero in radius; never a drawing/feature-size tolerance."""
    return numerical_bor_axis_tolerance(points)

def _segments_intersect_2d(
    a: 'np.ndarray',
    b: 'np.ndarray',
    c: 'np.ndarray',
    d: 'np.ndarray',
    tol: 'float',
) -> 'bool':
    """Inclusive segment intersection with a length-scaled cross tolerance."""

    def cross(p, q, r) -> 'float':
        return float((q[0] - p[0]) * (r[1] - p[1])
                     - (q[1] - p[1]) * (r[0] - p[0]))

    def on_segment(p, q, r, cross_tol) -> 'bool':
        return (
            abs(cross(p, q, r)) <= cross_tol
            and min(p[0], r[0]) - tol <= q[0] <= max(p[0], r[0]) + tol
            and min(p[1], r[1]) - tol <= q[1] <= max(p[1], r[1]) + tol
        )

    length_scale = max(
        float(np.linalg.norm(b - a)),
        float(np.linalg.norm(d - c)),
        tol,
    )
    cross_tol = tol * length_scale
    o1 = cross(a, b, c)
    o2 = cross(a, b, d)
    o3 = cross(c, d, a)
    o4 = cross(c, d, b)
    if (
        ((o1 > cross_tol and o2 < -cross_tol)
         or (o1 < -cross_tol and o2 > cross_tol))
        and ((o3 > cross_tol and o4 < -cross_tol)
             or (o3 < -cross_tol and o4 > cross_tol))
    ):
        return True
    return (
        on_segment(a, c, b, cross_tol)
        or on_segment(a, d, b, cross_tol)
        or on_segment(c, a, d, cross_tol)
        or on_segment(c, b, d, cross_tol)
    )

def _validate_solve_bor_generatrix(points, formulation: 'str') -> 'np.ndarray':
    """Validate the direct single-surface ``solve_bor`` geometry.

    EFIE may represent an open shell.  CFIE/MFIE require the supported
    closed-body topology: both ends on the rotation axis and traversal from
    the +z pole to the -z pole.  Every path rejects intersections because a
    self-crossing meridian generates an overlapping/non-manifold surface.
    """

    raw = np.asarray(points)
    if raw.ndim != 2 or raw.shape[1:] != (2,) or raw.shape[0] < 2:
        raise ValueError(
            "BoR generatrix must be a finite (N, 2) array of (rho, z) "
            "nodes with N >= 2."
        )
    if np.iscomplexobj(raw) and np.any(np.imag(raw) != 0.0):
        raise ValueError("BoR generatrix coordinates must be real.")
    try:
        pts = np.asarray(np.real(raw), dtype=float).copy()
    except (TypeError, ValueError) as exc:
        raise ValueError("BoR generatrix coordinates must be real numbers.") from exc
    if not np.all(np.isfinite(pts)):
        raise ValueError("BoR generatrix coordinates must all be finite.")

    diag = max(
        float(np.ptp(pts[:, 0])),
        float(np.ptp(pts[:, 1])),
        1.0e-15,
    )
    geom_tol = max(1.0e-14, 1.0e-10 * diag)
    axis_tol = _bor_axis_tolerance(pts)
    if np.any(pts[:, 0] < -axis_tol):
        bad = float(np.min(pts[:, 0]))
        raise ValueError(
            f"BoR generatrix rho coordinates must be >= 0; found {bad:.6g}."
        )
    pts[np.abs(pts[:, 0]) <= axis_tol, 0] = 0.0

    lengths = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    if np.any(lengths <= geom_tol):
        idx = int(np.argmin(lengths))
        raise ValueError(
            f"BoR generatrix element {idx} has zero or near-zero length "
            f"({lengths[idx]:.3g})."
        )
    if float(np.max(pts[:, 0])) <= axis_tol:
        raise ValueError(
            "BoR generatrix lies entirely on the rotation axis and sweeps "
            "zero surface area."
        )
    # Only the two end points may lie on the axis. An interior axis node is a
    # pinched (non-manifold) surface, and an element on the axis sweeps no
    # area: its rows vanish and the system loses rank (LAPACK info = 1,
    # condition 1e37 on a graded needle tip whose inner nodes a mesher had
    # snapped onto the axis).
    interior = np.flatnonzero(pts[1:-1, 0] == 0.0) + 1
    if interior.size:
        index = int(interior[0])
        raise ValueError(
            f"BoR generatrix node {index} of {len(pts)} (rho = {float(raw[index, 0].real):.3g}) "
            "lies on the rotation axis; only the end points may. A mesher "
            "that snaps small radii onto the axis must spare interior nodes.")


    n_elem = len(pts) - 1
    seg_a = pts[:-1]
    seg_b = pts[1:]
    mids = 0.5 * (seg_a + seg_b)
    half = 0.5 * lengths
    max_half = float(np.max(half))
    tree = cKDTree(mids)
    # A possible contact has center distance <= half[i]+half[j]+tol.
    # Let the longer panel own the pair, so a single long panel does not
    # inflate every short panel's query. Uniform meshes keep the cheaper
    # index ordering, whose bound is already within a factor of two.
    local_owner = max_half > 2.0 * float(np.min(half))
    roundoff = 32.0 * np.finfo(float).eps * max(float(np.max(np.abs(pts))), diag)
    checkpoint = current_checkpoint()
    for i in range(n_elem):
        if checkpoint is not None:
            checkpoint()
        radius = (2.0 * float(half[i]) if local_owner else float(half[i]) + max_half)
        radius += geom_tol + roundoff
        for candidate_index, j in enumerate(tree.query_ball_point(mids[i], radius)):
            if checkpoint is not None and candidate_index % 256 == 0:
                checkpoint()
            j = int(j)
            if local_owner:
                if abs(j - i) <= 1 or half[j] > half[i] or (half[j] == half[i] and j <= i):
                    continue
            elif j <= i + 1:
                continue
            lower = (
                float(np.linalg.norm(mids[i] - mids[j]))
                - float(half[i]) - float(half[j])
            )
            if lower > geom_tol + roundoff:
                continue
            if _segments_intersect_2d(
                pts[i], pts[i + 1], pts[j], pts[j + 1], geom_tol
            ):
                raise ValueError(
                    "BoR generatrix self-intersection/overlap between "
                    f"elements {i} and {j} is not supported."
                )

    start_on_axis = pts[0, 0] == 0.0
    end_on_axis = pts[-1, 0] == 0.0
    closed_body = start_on_axis and end_on_axis
    if formulation in {"cfie", "mfie"} and not closed_body:
        raise ValueError(
            f"{formulation.upper()} requires a closed BoR whose two "
            "generatrix endpoints lie on the rotation axis; use EFIE for "
            "an intentionally open shell."
        )
    if closed_body and not (pts[0, 1] > pts[-1, 1] + geom_tol):
        raise ValueError(
            "A closed BoR generatrix must be traversed from its +z axis "
            "endpoint to its -z axis endpoint so the left-of-travel normal "
            "faces the exterior."
        )
    from ghost_backend.bor.geometry import require_resolved_corners
    require_resolved_corners(pts)
    return pts

def _validated_bor_aspects(thetas_deg) -> 'np.ndarray':
    """Validate the direct-solver monostatic aspect grid."""

    thetas = np.atleast_1d(np.asarray(thetas_deg, dtype=float))
    if thetas.ndim != 1 or thetas.size == 0:
        raise ValueError("BoR aspect grid must be a non-empty one-dimensional array.")
    if not np.all(np.isfinite(thetas)):
        raise ValueError("BoR aspect angles must all be finite.")
    if np.any(thetas < 0.0) or np.any(thetas > 180.0):
        raise ValueError("BoR aspect angles must lie in [0, 180] degrees.")
    return thetas
