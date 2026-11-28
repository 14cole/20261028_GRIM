"""Does Local sizing depend on how one smooth PEC contour is split into named segments,
and what does each mesh cost in accuracy against a much denser reference?

  GRIM_ROOT=<95f8719> python segment_grouping.py results/segment_grouping

Fixture (mine, not Codex's): 96-sided PEC cylinder, radius 0.08 m, and a 96-sided dielectric
cylinder, radius 0.04 m, eps 9-0.05j, centres 0.6 m apart, 6 GHz, 180 angles, P1,
20 points per wavelength. Reference: Global sizing at 80 points per wavelength, P2.
"""
import json, sys
from pathlib import Path
import numpy as np
from common import solve, fields_of

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
ANGLES = np.arange(0.0, 360.0, 2.0)


def ring(radius, sides, center):
    t = -2 * np.pi * np.arange(sides + 1) / sides
    return np.column_stack((center[0] + radius * np.cos(t), center[1] + radius * np.sin(t)))


def geo(pieces, density):
    pec, die = ring(0.08, 96, (-0.3, 0.0)), ring(0.04, 96, (0.3, 0.05))
    lines = ["Title: grouping"]
    step = 96 // pieces
    for i in range(pieces):
        lines += [f"Segment: pec_{i} 2", f"properties: 2 -{density} 0 0 0"]
        lines += [" ".join(f"{v:.17g}" for v in (*a, *b)) for a, b in zip(pec[i*step:(i+1)*step], pec[i*step+1:(i+1)*step+1])]
    lines += ["Segment: rod 3", f"properties: 3 -{density} 0 1 0"]
    lines += [" ".join(f"{v:.17g}" for v in (*a, *b)) for a, b in zip(die[:-1], die[1:])]
    return "\n".join(lines + ["IBCS_Resistances:", "", "Dielectrics:", "1 9 -0.05 1 0"]) + "\n"


def run(tag, pieces, density, strategy, degree=1, backend="dense"):
    result, wall = solve(geo(pieces, density), 6.0, ANGLES, mesh_strategy=strategy, basis_order=degree, factorization=backend)
    f = fields_of(result); meta = result["metadata"]
    np.savez_compressed(out / f"{tag}.npz", angles_deg=ANGLES, TE=f["TE"], TM=f["TM"])
    return dict(tag=tag, pec_segments=pieces, points_per_wavelength=density, sizing=strategy, degree=degree,
                panels=meta.get("panel_count"), unknowns=meta.get("dense_largest_system") or meta.get("linear_node_count"),
                wall_s=round(wall, 2), quality_passed=(meta.get("quality_gate") or {}).get("passed")), f


rows = []
ref_row, ref = run("reference_global_80_p2", 1, 80, "global", degree=2)
alt_row, alt = run("reference_global_60_p2_compressed", 3, 60, "global", degree=2, backend="compressed")
def err(f, g=None):
    g = g or ref
    return {p: float(np.max(np.abs(f[p] - g[p])) / np.max(np.abs(g[p]))) for p in ("TE", "TM")}
alt_row["difference_from_reference"] = err(alt)
rows += [ref_row, alt_row]
for pieces in (1, 2, 3, 4):
    for strategy in ("local", "global"):
        row, f = run(f"{strategy}_{pieces}", pieces, 20, strategy)
        row["error_vs_reference"] = err(f)
        rows.append(row)
        print(row)
print(alt_row)
json.dump(rows, open(out / "summary.json", "w"), indent=1)
