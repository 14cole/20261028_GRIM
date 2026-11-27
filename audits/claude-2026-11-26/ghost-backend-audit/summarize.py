"""Collect the audit's raw results into tables. Usage: python summarize.py results > results/summary.json"""
import json, sys, statistics
from pathlib import Path
import numpy as np

root = Path(sys.argv[1]); out = {}
# A
rows = json.load(open(root/"a"/"summary.json")); table = {}
for r in rows:
    key = f"{r['fixture']} {r['ghz']:g} GHz"
    cell = table.setdefault(key, {}).setdefault(str(r["outer_sides"]), {})
    cell[r["requested"]] = dict(backend=r.get("linear_backend"), unknowns=r.get("largest_system"),
                                error_TM=r.get("error_TM"), error_TE=r.get("error_TE"), quality=r.get("quality_passed"))
    if "dense_vs_compressed_max_TM" in r:
        cell["dense_vs_compressed_max"] = max(r["dense_vs_compressed_max_TM"], r["dense_vs_compressed_max_TE"])
        cell["dense_vs_compressed_l2"] = max(r["dense_vs_compressed_l2_TM"], r["dense_vs_compressed_l2_TE"])
out["A_accuracy"] = table
out["A_worst_dense_vs_compressed_max"] = max(c["dense_vs_compressed_max"] for t in table.values() for c in t.values())
out["A_worst_dense_vs_compressed_l2"] = max(c["dense_vs_compressed_l2"] for t in table.values() for c in t.values())
out["A_all_quality_gates_passed"] = all(r.get("quality_passed") for r in rows)
# B
rows = json.load(open(root/"b"/"summary.json")); table = []
for r in rows:
    s = r["search"]; g = lambda pol, k: s.get(f"channel_metadata.{pol}.mesh_convergence.{k}")
    table.append(dict(
        fixture=r["fixture"], drawn_sides=r["drawn_outer_sides"], equal_area=r["equal_area_polygon"],
        certified=r["certified"], published=r["published_mesh"], backend=r["linear_backend"],
        base_panels=g("VV", "base_panel_count"), fine_panels=g("VV", "fine_panel_count"),
        reported_change_max=max(g("VV", "complex_max_normalized"), g("HH", "complex_max_normalized")),
        estimated_published_error_max=max(g("VV", "estimated_published_error.complex_max_normalized"),
                                          g("HH", "estimated_published_error.complex_max_normalized")),
        geometry_model=g("VV", "geometry_model"), geometry_approximation_certified=g("VV", "geometry_approximation_certified"),
        error_vs_circle_TM=r["error_vs_circle_TM"], error_vs_circle_TE=r["error_vs_circle_TE"],
        gap_m=r["polygon_to_circle_max_gap_m"],
        two_k_gap=None if r["polygon_to_circle_max_gap_m"] is None else 2*2*np.pi*r["ghz"]*1e9/299792458.0*r["polygon_to_circle_max_gap_m"]))
out["B_certification"] = table
# C  (a run is identified by its batch folder and tag: six tags recur across batches)
runs = []
for f in sorted(root.glob("c*/runs.jsonl")):
    for line in open(f):
        r = json.loads(line); r["batch"] = f.parent.name; r["npz"] = str(f.parent / f"{r['tag']}.npz"); runs.append(r)
for backend in ("compressed", "dense"):                      # the 24k pair was launched by hand
    f = root / "c_large" / f"{backend}.out"
    if f.exists() and f.read_text().strip():
        r = json.loads(f.read_text().strip().splitlines()[-1])
        r.update(batch="c_large", tag=f"s8448_a360_t4_{backend}", npz=str(root / "c_large" / f"s8448_a360_t4_{backend}.npz"))
        runs.append(r)
for mode in ("memory", "disk"):                              # forced residual-storage pair at 12k
    f = root / "c_residual" / f"{mode}.out"
    if f.exists() and f.read_text().strip():
        r = json.loads(f.read_text().strip().splitlines()[-1])
        r.update(batch="c_residual", tag=f"s4224_a360_t4_dense_{mode}", requested=f"dense[residual={mode}]",
                 npz=str(root / "c_residual" / f"s4224_a360_t4_dense_{mode}.npz"))
        runs.append(r)
out["C_run_count"] = len(runs)
out["C_archives_present"] = sum(Path(r["npz"]).exists() for r in runs)
groups = {}
for r in runs:
    if "solve_wall_s" in r:
        groups.setdefault((r["unknowns_per_system"], r["threads"], r["angles"], r["requested"]), []).append(r)
table = []
for (n, t, a, b), rs in sorted(groups.items()):
    w = [r["solve_wall_s"] for r in rs]; m = [r["peak_rss_gib"] for r in rs]
    table.append(dict(unknowns=n, threads=t, angles=a, requested=b, backend=rs[0]["linear_backend"], panels=rs[0]["panels"],
                      runs=len(rs), batches=sorted({r["batch"] for r in rs}), wall_s=w, wall_median_s=statistics.median(w),
                      wall_min_s=min(w), wall_max_s=max(w), peak_rss_gib=m, peak_rss_median_gib=statistics.median(m),
                      error_TM=rs[0]["error_TM"], error_TE=rs[0]["error_TE"], quality=all(r["quality_passed"] for r in rs)))
out["C_timing"] = table
load = lambda r: np.load(r["npz"])
worst = lambda x, y: max(float(np.max(np.abs(x[k] - y[k])) / np.max(np.abs(y[k]))) for k in ("ghost_TM", "ghost_TE"))
out["C_repeat_field_spread_max"] = max(worst(load(r), load(rs[0])) for rs in groups.values() for r in rs)
out["C_dense_vs_compressed_max"] = {
    f"{n}_{t}_{a}": worst(load(groups[(n, t, a, "compressed")][0]), load(rs[0]))
    for (n, t, a, b), rs in groups.items() if b == "dense" and (n, t, a, "compressed") in groups}
print(json.dumps(out, indent=1, default=float))
