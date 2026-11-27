"""Fixtures and solve wrappers for the backend audit.

GRIM_ROOT must be a checkout (or `git archive` export) of ed90b65.
"""
import os, sys, time
from pathlib import Path
import numpy as np

GRIM_ROOT = Path(os.environ["GRIM_ROOT"])
sys.path.insert(0, str(GRIM_ROOT / "tools" / "GHOST"))
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot  # noqa: E402
from ghost_backend.execution.options import cpu_allocation_scope  # noqa: E402
from ghost_backend.twod.solver import solve_monostatic_rcs_2d, solve_monostatic_rcs_2d_certified  # noqa: E402


def _ring(radius, sides, center, phase=0.0):
    t = phase - 2 * np.pi * np.arange(sides) / sides          # clockwise, as the shipped examples
    p = np.column_stack((center[0] + radius * np.cos(t), center[1] + radius * np.sin(t)))
    return [" ".join(f"{v:.17g}" for v in (*a, *b)) for a, b in zip(p, np.roll(p, -1, axis=0))]


def cylinder_geo(b, sides, a=None, eps=None, mu=1.0, center=(0.0, 0.0), n=1, inner_sides=None,
                 equal_area=False):
    """Regular polygon(s) inscribed in the circle(s), one primitive per side.

    n is the per-primitive panel request (1 = one panel per side; 0 = wavelength sizing).
    equal_area scales each polygon so its area equals the circle's.
    """
    def scale(m):
        return np.sqrt((2 * np.pi / m) / np.sin(2 * np.pi / m)) if equal_area else 1.0
    lines = ["Title: audit cylinder"]
    if a is None:
        lines += ["Segment: pec 2", f"properties: 2 {n} 0 0 0"] + _ring(b * scale(sides), sides, center)
        diel = []
    else:
        m = inner_sides or max(8, int(round(sides * a / b / 8.0)) * 8)
        lines += ["Segment: coat_outer 3", f"properties: 3 {n} 0 1 0"] + _ring(b * scale(sides), sides, center)
        lines += ["Segment: coat_inner 4", f"properties: 4 {n} 0 1 0"] + _ring(a * scale(m), m, center)
        e, u = complex(eps), complex(mu)
        diel = [f"1 {e.real:.17g} {e.imag:.17g} {u.real:.17g} {u.imag:.17g}"]
    lines += ["IBCS_Resistances:", "", "Dielectrics:"] + diel
    return "\n".join(lines) + "\n"


def snapshot(text):
    parsed = parse_geometry(text)
    return build_geometry_snapshot(*parsed) if isinstance(parsed, tuple) else build_geometry_snapshot(parsed)


def fields_of(result):
    """{'TE': complex array, 'TM': complex array} in request order (VV is TE, HH is TM)."""
    out = {}
    for label, pol in (("VV", "TE"), ("HH", "TM")):
        rows = result["co_solved_samples"][label]
        out[pol] = np.array([complex(r["rcs_amp_real"], r["rcs_amp_imag"]) for r in rows])
    return out


def facts(result):
    meta = result.get("metadata", {})
    gate = meta.get("quality_gate", {}) or {}
    keep = {}
    for key in ("linear_backend", "panel_count", "panels", "n_panels", "unknowns", "system_dofs", "n_unknowns",
                "basis_order", "mesh_strategy", "mesh_convergence_certified", "solver_method"):
        if key in meta:
            keep[key] = meta[key]
    keep["quality_passed"] = gate.get("passed")
    keep["warnings"] = meta.get("warnings")
    return keep


def solve_fixed(text, f_ghz, angles, backend, threads=1, basis_order=1, ram_gib=None, batch=256, **more):
    """One specified mesh, no convergence search."""
    opts = dict(factorization=backend, basis_order=basis_order, mesh_strategy="global",
                assembly_threads=threads, blas_threads=threads, rhs_compression="off", angle_batch_size=batch)
    if ram_gib is not None:
        opts["ram_budget_gib"] = ram_gib
    opts.update(more)
    t = time.perf_counter()
    with cpu_allocation_scope(threads):
        result = solve_monostatic_rcs_2d(snapshot(text), [float(f_ghz)], [float(x) for x in angles],
                                         geometry_units="meters", strict_quality_gate=True,
                                         execution_options=opts)
    return result, time.perf_counter() - t


def rel(got, ref):
    """max |got - ref| / max |ref|."""
    return float(np.max(np.abs(np.asarray(got) - np.asarray(ref))) / np.max(np.abs(ref)))
