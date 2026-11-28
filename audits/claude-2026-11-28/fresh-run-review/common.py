"""Shared setup: GRIM_ROOT must be a checkout or export of main at 95f8719."""
import os, sys, time
from pathlib import Path
import numpy as np
ROOT = Path(os.environ["GRIM_ROOT"])
sys.path.insert(0, str(ROOT / "tools" / "GHOST"))
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot  # noqa: E402
from ghost_backend.execution.options import cpu_allocation_scope  # noqa: E402
import ghost_backend.twod.solver as solver  # noqa: E402
import ghost_backend.execution.selection as selection  # noqa: E402


def snapshot(text):
    parsed = parse_geometry(text)
    return build_geometry_snapshot(*parsed) if isinstance(parsed, tuple) else build_geometry_snapshot(parsed)


def fields_of(result):
    out = {}
    for label, pol in (("VV", "TE"), ("HH", "TM")):
        rows = result["co_solved_samples"][label]
        out[pol] = np.array([complex(r["rcs_amp_real"], r["rcs_amp_imag"]) for r in rows])
    return out


def solve(text, ghz, angles, threads=2, **options):
    opts = dict(assembly_threads=threads, blas_threads=threads, rhs_compression="off")
    opts.update(options)
    t = time.perf_counter()
    with cpu_allocation_scope(threads):
        result = solver.solve_monostatic_rcs_2d(snapshot(text), [float(ghz)], [float(a) for a in angles],
                                                geometry_units="meters", strict_quality_gate=True,
                                                execution_options=opts)
    return result, time.perf_counter() - t
