"""One Automatic-mesh (Standard target) airfoil solve in a fresh process.

  GRIM_ROOT=<95f8719> python airfoil_job.py <ghz> <angles> <auto|dense|compressed> <out.npz>

Times the solver call only: no recovery records, no GRIM export.
"""
import json, sys, time
import numpy as np
from common import ROOT, snapshot, fields_of, solver
from ghost_backend.execution.options import efficient_defaults, cpu_allocation_scope
from ghost_backend.runs.quality import accuracy_target_policy

ghz, n, backend, out = float(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4]
angles = np.arange(n) * (360.0 / n) if n == 360 else np.arange(float(n))
options = dict(efficient_defaults(), assembly_threads=2, blas_threads=2)
if backend != "auto":
    options["factorization"] = backend
text = (ROOT / "airfoil.geo").read_text()
t = time.perf_counter()
with cpu_allocation_scope(2):
    result = solver.solve_monostatic_rcs_2d_certified(
        geometry_snapshot=snapshot(text), frequencies_ghz=[ghz], elevations_deg=angles.tolist(),
        geometry_units="inches", mesh_convergence_policy=accuracy_target_policy("standard"), execution_options=options)
wall = time.perf_counter() - t
F = fields_of(result); meta = result["metadata"]
np.savez_compressed(out, angles_deg=angles, TE=F["TE"], TM=F["TM"])
hwm = [int(l.split()[1]) for l in open("/proc/self/status") if l.startswith("VmHWM")][0] / 2**20
print(json.dumps(dict(ghz=ghz, angles=n, requested=backend, linear_backend=meta.get("linear_backend"),
    panels=meta.get("panel_count"), unknowns=meta.get("dense_largest_system") or meta.get("linear_node_count"),
    degree=meta.get("polynomial_degree"), certified=meta.get("mesh_convergence_certified"),
    quality_passed=(meta.get("quality_gate") or {}).get("passed"), wall_s=round(wall, 2), peak_rss_gib=round(hwm, 3),
    stage_seconds=(meta.get("runtime_profile") or {}).get("stage_seconds"))))
