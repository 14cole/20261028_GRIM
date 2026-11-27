"""One timed solve in a fresh process (Study C). Prints one JSON line.

    GRIM_ROOT=<ed90b65> python timed_job.py <outer_sides> <dense|compressed> <n_angles> <threads> <out.npz> [ghz]
"""
import json, os, sys, time
t_start = time.perf_counter()
sides, backend, n_angles, threads, out = int(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
ghz = float(sys.argv[6]) if len(sys.argv) > 6 else 10.0
for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[var] = str(threads)
import numpy as np
from harness import *
import reference as ref

FX = dict(a=0.10, b=0.12, eps=2.8 - 0.06j, mu=1.0)
CENTER = (0.031, -0.017)
angles = np.arange(n_angles) * (360.0 / n_angles)
text = cylinder_geo(sides=sides, center=CENTER, **FX)


def status(key):
    for line in open("/proc/self/status"):
        if line.startswith(key + ":"):
            return int(line.split()[1]) / 1024.0 ** 2          # GiB
    return None


rss_before = status("VmRSS")
extra = json.loads(os.environ.get("GHOST_AUDIT_OPTIONS", "{}"))      # e.g. {"dense_residual_storage": "disk"}
result, solve_wall = solve_fixed(text, ghz, angles, backend, threads=threads, **extra)
F = fields_of(result); meta = result["metadata"]
exact = {pol: ref.stored_amplitude(pol, ghz, angles, center=CENTER, **FX) for pol in ("TM", "TE")}
np.savez_compressed(out, angles_deg=angles, ghost_TM=F["TM"], ghost_TE=F["TE"],
                    analytic_TM=exact["TM"], analytic_TE=exact["TE"])
mem = meta.get("memory_accounting") or {}
print(json.dumps(dict(
    outer_sides=sides, requested=backend, angles=n_angles, threads=threads, ghz=ghz, extra_options=extra,
    residual_storage_requested=(meta.get("execution_options") or {}).get("dense_residual_storage"),
    linear_backend=meta.get("linear_backend"), solver_method=meta.get("solver_method"),
    panels=meta.get("panel_count"), unknowns_per_system=meta.get("dense_largest_system") or meta.get("linear_node_count"),
    nodes=meta.get("linear_node_count"), polynomial_degree=meta.get("polynomial_degree"),
    quality_passed=(meta.get("quality_gate") or {}).get("passed"), residual_max=meta.get("residual_norm_max"),
    warnings=meta.get("warnings"), rhs_compression=meta.get("cpu_rhs_compression_requested"),
    solve_wall_s=round(solve_wall, 3), process_wall_s=round(time.perf_counter() - t_start, 3),
    rss_before_solve_gib=round(rss_before, 3), peak_rss_gib=round(status("VmHWM"), 3),
    error_TM=rel(F["TM"], exact["TM"]), error_TE=rel(F["TE"], exact["TE"]),
    memory_accounting={k: v for k, v in mem.items() if isinstance(v, (int, float, str, bool))},
), default=str))
