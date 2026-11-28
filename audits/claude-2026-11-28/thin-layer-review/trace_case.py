"""One traced thin-layer solve in a fresh process.

  GRIM_ROOT=<tree> python trace_case.py <label> <fixture> <backend> <outdir> [mode]

fixture: <panels>:<variant>   variant in one|three|six|six_mixed|many|ring|two_strips
backend: dense | compressed | automatic        mode: mono (default) | bistatic | plan_only
GHOST_MAX_SOLVE_GB, if set, is the controlled RAM reservation. THIN_MATERIAL ("eps_re eps_im mu_re mu_im"),
THIN_BASIS and THIN_TAG vary the layer material, the basis order and the output name.

Logged: every desktop and HPC forecast, every solve-time memory estimate, the operator handed to the
linear solver (type and shape), the right-hand-side shape, all numeric sample columns, peak RSS.
"""
import json, os, sys, tempfile, time
from pathlib import Path
import numpy as np

ROOT = Path(os.environ["GRIM_ROOT"]); sys.path.insert(0, str(ROOT / "tools" / "GHOST"))
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
from ghost_backend.execution.options import cpu_allocation_scope, execution_scope, validate_options
import ghost_backend.twod.solver as solver
import ghost_backend.execution.selection as selection
import ghost_backend.hpc.scheduler as hpc
from ghost_backend.compressed import hmatrix

label, fixture, backend, outdir = sys.argv[1:5]
mode = sys.argv[5] if len(sys.argv) > 5 else "mono"
out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
GHZ, STEP = 3.0, 0.005                       # 20 panels per free-space wavelength
panels_total, variant = fixture.split(":"); panels_total = int(panels_total)


def polyline(counts, turn_deg=1.0):
    """Vertices of straight pieces with counts[i] panels each and a small turn at every joint."""
    pts, heading, p = [np.zeros(2)], 0.0, np.zeros(2)
    for i, n in enumerate(counts):
        heading += np.deg2rad(turn_deg) * (1 if i % 2 else -1) * (i > 0)
        p = p + n * STEP * np.array([np.cos(heading), np.sin(heading)])
        pts.append(p)
    return pts


def geometry():
    if variant == "ring":
        k = 8; n = panels_total // k
        r = panels_total * STEP / (2 * np.pi)
        t = 2 * np.pi * np.arange(k * 12 + 1) / (k * 12)          # 96 chords, one panel count each
        pts = [r * np.array([np.cos(a), np.sin(a)]) for a in t]
        pieces = [(pts[i], pts[i + 1], max(1, panels_total // (k * 12))) for i in range(k * 12)]
        groups = [list(range(g * 12, (g + 1) * 12)) for g in range(k)]
        reverse, order = {1, 4, 6}, [3, 0, 7, 1, 5, 2, 6, 4]
    elif variant == "two_strips":
        a = polyline([panels_total // 4] * 2); b = [p + np.array([0.0, 0.2]) for p in polyline([panels_total // 4] * 2)]
        pieces = [(a[0], a[1], panels_total // 4), (a[1], a[2], panels_total // 4),
                  (b[0], b[1], panels_total // 4), (b[1], b[2], panels_total // 4)]
        groups, reverse, order = [[0], [1], [2], [3]], {1, 2}, [2, 0, 3, 1]
    else:
        if variant == "many":
            counts = [3] * (panels_total // 3)
        else:
            counts = [panels_total // 6] * 5; counts.append(panels_total - sum(counts))
        pts = polyline(counts, turn_deg=0.2 if variant == "many" else 1.0)
        pieces = [(pts[i], pts[i + 1], counts[i]) for i in range(len(counts))]
        m = len(pieces)
        if variant == "one":
            groups, reverse, order = [list(range(m))], set(), [0]
        elif variant == "three":
            groups, reverse, order = [[0, 1], [2, 3], [4, 5]], set(), [0, 1, 2]
        elif variant == "six":
            groups, reverse, order = [[i] for i in range(m)], set(), list(range(m))
        elif variant == "six_mixed":
            groups, reverse, order = [[0], [1, 2], [3], [4], [5]], {1, 3}, [3, 0, 4, 1, 2]
        elif variant == "many":
            groups, reverse = [[i] for i in range(m)], set(range(1, m, 2))
            order = list(np.random.default_rng(3).permutation(m))
        else:
            raise SystemExit("unknown variant")
    lines = ["Title: thin layer " + fixture]
    for g in order:
        lines += [f"Segment: part_{g} 1"]
        members = groups[g][::-1] if g in reverse else groups[g]
        first = True
        for i in members:
            a, b, n = pieces[i]
            if g in reverse:
                a, b = b, a
            if first:
                lines.append(f"properties: 1 {n} 10 0 0"); first = False
            lines.append(" ".join(f"{v:.17g}" for v in (*a, *b)))
    return "\n".join(lines + ["IBCS_Resistances:", "10 thin_dielectric 0.0005 50", "", "Dielectrics:", "50 " + os.environ.get("THIN_MATERIAL", "3.2 -0.02 1 0")]) + "\n"


TEXT = geometry()
(out / f"{fixture.replace(':', '_')}.geo").write_text(TEXT)
log, where = [], ["execution"]

real_resources = solver._dense_formulation_resources
def resources(mesh, infos, pol, *a, **k):
    r = real_resources(mesh, infos, pol, *a, **k)
    log.append(dict(event="resources", source=where[0], pol=pol, system_dofs=int(r["system_dofs"]), nodes=int(len(mesh.nodes)),
                    elements=int(len(mesh.elements)), hierarchical_storage_priced="hmatrix_storage" in r))
    return r
solver._dense_formulation_resources = resources

real_estimate = solver._estimate_memory_gb
def estimate(*a, **k):
    value = real_estimate(*a, **k)
    res = k.get("dense_resources") or {}
    from ghost_backend.linalg.hierarchical import factor_mode
    log.append(dict(event="estimate", source=where[0], system_dofs=int(k.get("system_dofs") or 0), gib=float(value),
                    factor_mode=factor_mode(), live=bool(k.get("activate_memory_plan")),
                    hierarchical_storage_priced="hmatrix_storage" in res, sampled_storage_priced="compressed_storage" in res,
                    formulation=res.get("formulation"),
                    plan_model=(res.get("memory_estimate") or {}).get("model")))
    return value
solver._estimate_memory_gb = estimate

real_solve = solver._solve_fields
def solve_fields(mesh, matrix, k0, angles, rhs_builder, *a, **k):
    entry = dict(event="operator", type=type(matrix).__name__, module=type(matrix).__module__,
                 shape=[int(v) for v in getattr(matrix, "shape", ())], mesh_nodes=int(len(mesh.nodes)), rhs_shapes=[])
    log.append(entry)
    def builder(batch):
        rhs = rhs_builder(batch)
        entry["rhs_shapes"].append([int(v) for v in np.shape(rhs)])
        return rhs
    return real_solve(mesh, matrix, k0, angles, builder, *a, **k)
solver._solve_fields = solve_fields

real_forecast = selection._forecast_backend
def forecast(*a, **k):
    where[0] = "desktop_forecast"
    try: return real_forecast(*a, **k)
    finally: where[0] = "execution"
selection._forecast_backend = forecast


def snapshot():
    parsed = parse_geometry(TEXT)
    return build_geometry_snapshot(*parsed) if isinstance(parsed, tuple) else build_geometry_snapshot(parsed)


ANGLES = np.arange(0.0, 360.0, 1.5)           # 240 monostatic angles
options = dict(assembly_threads=1, blas_threads=1, rhs_compression="off", mesh_strategy="global", basis_order=int(os.environ.get("THIN_BASIS", "1")))
if backend != "automatic":
    options["factorization"] = backend
report = dict(tree=label, fixture=fixture, backend=backend, mode=mode, ram_cap_gib=os.environ.get("GHOST_MAX_SOLVE_GB"),
              hierarchical_cutoff=int(hmatrix.minimum_unknowns()))

# HPC planner, public entry point, both channel orders.
where[0] = "hpc_forecast"
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "layer.geo"; path.write_text(TEXT)
    for order in (("VV", "HH"), ("HH", "VV")):
        try:
            with execution_scope(validate_options(dict(options))):
                plan = hpc.predict_2d_resources_many(str(path), [GHZ], list(order), "meters", solver.MAX_PANELS_DEFAULT,
                                                     n_angles=len(ANGLES), solver_method="auto")
            report["hpc_" + "_".join(order)] = {pol: dict(system_dofs=rec["system_dofs"], peak_gb=rec["peak_gb"],
                candidates={m: c.get("peak_gb") for m, c in (rec.get("backend_candidates") or {}).items()})
                for (_, pol), rec in plan.items()}
        except Exception as exc:
            report["hpc_" + "_".join(order)] = type(exc).__name__ + ": " + str(exc)[:200]
where[0] = "execution"

rss0 = [int(l.split()[1]) for l in open("/proc/self/status") if l.startswith("VmRSS")][0] / 2**20
t = time.perf_counter()
try:
    if mode == "plan_only":
        report["outcome"] = "planned"
    else:
        with cpu_allocation_scope(1):
            if mode == "bistatic":
                result = solver.solve_bistatic_rcs_2d(snapshot(), [GHZ], [0.0, 40.0, 95.0], np.arange(0.0, 360.0, 3.0).tolist(),
                                                      geometry_units="meters", strict_quality_gate=True, execution_options=options)
            else:
                result = solver.solve_monostatic_rcs_2d(snapshot(), [GHZ], ANGLES.tolist(), geometry_units="meters",
                                                        strict_quality_gate=True, execution_options=options)
        report["outcome"] = "solved"
        meta = result["metadata"]
        arrays = {}
        for channel, rows in (result.get("co_solved_samples") or {}).items():
            rows = list(rows)
            for key in sorted(rows[0]):
                try:
                    arrays[f"{channel}_{key}"] = np.array([float(r[key]) for r in rows])
                except (TypeError, ValueError):
                    pass
        np.savez_compressed(out / (f"{label}_{fixture.replace(':', '_')}_{backend}_{mode}" + os.environ.get("THIN_TAG", "") + ".npz"), **arrays)
        report.update(linear_backend=meta.get("linear_backend"), residual_norm_max=meta.get("residual_norm_max"),
                      quality_passed=(meta.get("quality_gate") or {}).get("passed"),
                      thin_layer_evidence=[{k: e.get(k) for k in ("polarization", "unknowns", "estimated_peak_gib")}
                                           for ch in (meta.get("thin_layer") or {}).values() for e in (ch if isinstance(ch, list) else [ch])]
                      if isinstance(meta.get("thin_layer"), dict) else None)
except MemoryError as exc:
    report["outcome"] = "refused: " + str(exc)[:240]
except Exception as exc:
    report["outcome"] = type(exc).__name__ + ": " + str(exc)[:240]
report.update(wall_s=round(time.perf_counter() - t, 2), rss_before_gib=round(rss0, 4),
              peak_rss_gib=round([int(l.split()[1]) for l in open("/proc/self/status") if l.startswith("VmHWM")][0] / 2**20, 4), log=log)
tag = f"{label}_{fixture.replace(':', '_')}_{backend}_{mode}" + os.environ.get("THIN_TAG", "") + (f"_cap{os.environ['GHOST_MAX_SOLVE_GB']}" if os.environ.get("GHOST_MAX_SOLVE_GB") else "")
json.dump(report, open(out / f"{tag}.json", "w"), indent=1)

def last(source, pol=None, event="resources"):
    hits = [e for e in log if e["event"] == event and e["source"] == source and (pol is None or e.get("pol") == pol)]
    return hits[-1]["system_dofs"] if hits else None
ops = [(e["type"], e["shape"], e["rhs_shapes"][:1]) for e in log if e["event"] == "operator"]
print(label, fixture, backend, report["outcome"][:60], "| desktop TE/TM", last("desktop_forecast", "TE"), last("desktop_forecast", "TM"),
      "| hpc", {k: (v if isinstance(v, str) else {p: r["system_dofs"] for p, r in v.items()}) for k, v in report.items() if k.startswith("hpc_")},
      "| exec TE/TM", last("execution", "TE"), last("execution", "TM"), "| operators", ops, "| backend", report.get("linear_backend"),
      "| rss", report["peak_rss_gib"])
