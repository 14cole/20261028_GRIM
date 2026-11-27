"""Study A: both backends against the analytic series on specified meshes.

    GRIM_ROOT=<ed90b65> python study_a_accuracy.py results/a
"""
import json, sys, traceback
from pathlib import Path
import numpy as np
from harness import *
import reference as ref

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
ANGLES = np.arange(0.0, 360.0, 1.0)
CENTER = (0.031, -0.017)
FIXTURES = {
    "pec": dict(b=0.050),
    "coat": dict(a=0.040, b=0.050, eps=2.8 - 0.06j, mu=1.0),
    "coat-magnetic": dict(a=0.040, b=0.050, eps=4.0 - 0.5j, mu=1.5 - 0.3j),
    "coat-thick": dict(a=0.030, b=0.060, eps=2.8 - 0.06j, mu=1.0),
}
CASES = [("pec", 3.0), ("pec", 10.0), ("coat", 3.0), ("coat", 10.0), ("coat-magnetic", 6.0), ("coat-thick", 6.0)]
SIDES = [128, 256, 512, 1024]
rows = []
for name, f in CASES:
    fx = FIXTURES[name]
    exact = {pol: ref.stored_amplitude(pol, f, ANGLES, center=CENTER, **fx) for pol in ("TM", "TE")}
    for sides in SIDES:
        text = cylinder_geo(sides=sides, center=CENTER, **fx)
        got = {}
        for backend in ("dense", "compressed"):
            tag = f"{name}_{f:g}GHz_{sides}_{backend}"
            row = dict(fixture=name, ghz=f, outer_sides=sides, requested=backend)
            try:
                result, wall = solve_fixed(text, f, ANGLES, backend)
                F = fields_of(result); got[backend] = F
                meta = result["metadata"]
                row.update(wall_s=round(wall, 2), linear_backend=meta.get("linear_backend"),
                           solver_method=meta.get("solver_method"), panels=meta.get("panel_count"),
                           nodes=meta.get("linear_node_count"), largest_system=meta.get("dense_largest_system"),
                           quality_passed=(meta.get("quality_gate") or {}).get("passed"),
                           residual_max=meta.get("residual_norm_max"), warnings=meta.get("warnings"),
                           error_TM=rel(F["TM"], exact["TM"]), error_TE=rel(F["TE"], exact["TE"]))
                np.savez_compressed(out / f"{tag}.npz", angles_deg=ANGLES, ghost_TM=F["TM"], ghost_TE=F["TE"],
                                    analytic_TM=exact["TM"], analytic_TE=exact["TE"])
            except Exception as exc:
                row.update(failed=f"{type(exc).__name__}: {str(exc)[:300]}")
            if backend == "compressed" and "dense" in got and "compressed" in got:
                for pol in ("TM", "TE"):
                    d, c = got["dense"][pol], got["compressed"][pol]
                    row[f"dense_vs_compressed_max_{pol}"] = rel(c, d)
                    row[f"dense_vs_compressed_l2_{pol}"] = float(np.linalg.norm(c - d) / np.linalg.norm(d))
            rows.append(row)
            print(json.dumps(row, default=str), flush=True)
            (out / "summary.json").write_text(json.dumps(rows, indent=1, default=str) + "\n")
