"""Study B: what the shipped Automatic workflow's mesh certificate establishes.

The same circle is drawn as inscribed polygons of different side counts and
solved with 'Find converged mesh automatically', standard target, automatic
backend, wavelength sizing (N = 0), exactly as the GUI requests it.

    GRIM_ROOT=<ed90b65> python study_b_certification.py results/b
"""
import json, sys, time
from pathlib import Path
import numpy as np
from harness import *
import reference as ref
from ghost_backend.execution.options import efficient_defaults
from ghost_backend.runs.quality import accuracy_target_policy

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
ANGLES = np.arange(0.0, 360.0, 1.0)
CENTER = (0.031, -0.017)
F = 6.0
FIXTURES = {"pec": dict(b=0.050), "coat": dict(a=0.040, b=0.050, eps=2.8 - 0.06j, mu=1.0)}
POLICY = accuracy_target_policy("standard")


def scalars(d, prefix=""):
    """Flatten the metadata entries that describe the mesh search."""
    keep = {}
    if isinstance(d, dict):
        for k, v in d.items():
            name = f"{prefix}{k}"
            if isinstance(v, (int, float, str, bool)) or v is None:
                if any(w in name.lower() for w in ("mesh", "certif", "converg", "change", "panel", "degree", "node",
                                                   "backend", "refin", "target", "tolerance", "passed", "delta", "diff")):
                    keep[name] = v
            elif isinstance(v, dict) and len(prefix) < 120:
                keep.update(scalars(v, name + "."))
    return keep


rows = []
(out / "policy.json").write_text(json.dumps(POLICY, indent=1, default=str) + "\n")
for name, fx in FIXTURES.items():
    exact = {pol: ref.stored_amplitude(pol, F, ANGLES, center=CENTER, **fx) for pol in ("TM", "TE")}
    for sides, equal_area in ((16, False), (32, False), (64, False), (360, False), (16, True), (32, True)):
        inner = None if "a" not in fx else max(8, int(round(sides * 0.8 / 4)) * 4)
        text = cylinder_geo(sides=sides, center=CENTER, n=0, inner_sides=inner, equal_area=equal_area, **fx)
        row = dict(fixture=name, ghz=F, drawn_outer_sides=sides, drawn_inner_sides=inner, equal_area_polygon=equal_area,
                   polygon_to_circle_max_gap_m=float(fx["b"] * (1 - np.cos(np.pi / sides))) if not equal_area else None)
        t = time.perf_counter()
        try:
            result = solve_monostatic_rcs_2d_certified(
                geometry_snapshot=snapshot(text), frequencies_ghz=[F], elevations_deg=ANGLES.tolist(),
                geometry_units="meters", mesh_convergence_policy=POLICY, execution_options=efficient_defaults())
            Fd = fields_of(result); meta = result["metadata"]
            row.update(wall_s=round(time.perf_counter() - t, 2), certified=meta.get("mesh_convergence_certified"),
                       published_mesh=meta.get("published_mesh"), linear_backend=meta.get("linear_backend"),
                       panels=meta.get("panel_count"), polynomial_degree=meta.get("polynomial_degree"),
                       nodes=meta.get("linear_node_count"), quality_passed=(meta.get("quality_gate") or {}).get("passed"),
                       warnings=meta.get("warnings"),
                       error_vs_circle_TM=rel(Fd["TM"], exact["TM"]), error_vs_circle_TE=rel(Fd["TE"], exact["TE"]),
                       search=scalars({k: v for k, v in meta.items() if k not in ("execution_options", "runtime_profile")}))
            tag = f"{name}_{sides}{'_equal_area' if equal_area else ''}"
            np.savez_compressed(out / f"{tag}.npz", angles_deg=ANGLES, ghost_TM=Fd["TM"], ghost_TE=Fd["TE"],
                                analytic_TM=exact["TM"], analytic_TE=exact["TE"])
            (out / f"{tag}_metadata.json").write_text(json.dumps(
                {k: v for k, v in meta.items() if k != "runtime_profile"}, indent=1, default=str)[:400000] + "\n")
        except Exception as exc:
            row.update(wall_s=round(time.perf_counter() - t, 2), failed=f"{type(exc).__name__}: {str(exc)[:400]}")
        rows.append(row); print(json.dumps({k: v for k, v in row.items() if k != "search"}, default=str), flush=True)
        (out / "summary.json").write_text(json.dumps(rows, indent=1, default=str) + "\n")
