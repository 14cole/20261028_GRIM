"""Run the shipped and corrected GHOST Dense solvers in separate native Windows processes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

import numpy as np
import psutil

# Normalize text newlines for checkouts using core.autocrlf on Windows.
SOURCES = {
    "execution/dense_memory.py": ("446372033a95ef5a30b813fe1864fd8d3d1e0b2bc7472c3e441aa6fa6059644e", "94b759d05c15e061559fd8b06707d5a707a70aaecdaae375e7c327403da562b7"),
    "execution/residency.py": (None, "8b9936565af903a65edcf435f2a0e588a5fd50e2166250398b72b49d51e7e212"),
    "twod/assembly/session.py": ("7b547e5f167b909be65ef9c033263912014199069e397ba266b8ee2258687407", "aacb8d3719f22f8d0d322401a20afc0022c17de6ceb839b347b087310393b74a"),
    "twod/formulations/dielectric.py": ("a5ee5fba6bb92f751adbed9fd527ea6779bb2dc12cf0d1786e026ff6627ecaca", "cd5074f25a799551cfcf67a5da323b9453d96fae101b918a75d5ac16dcb74cc5"),
    "twod/solver.py": ("77dc176e95c4e74277d65ce8a497a2e9710fd31191e15e961ecde66d6ecba902", "2c498336cb00d885fb81bc8eed667ee28811da31d685578479edb8a756e6ff7f"),
}


def dump(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def check_sources(roots):
    for i, (label, root) in enumerate(roots.items()):
        for name, expected in SOURCES.items():
            path = root / "tools/GHOST/ghost_backend" / name
            digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() if path.exists() else None
            if digest != expected[i]:
                raise ValueError(f"Unexpected {label} source at {name}: {digest}")


def mixed_geometry(harness, sides):
    def sections_and_material(body):
        segments, materials = body.split("IBCS_Resistances:")
        return "Segment:" + segments.split("Segment:", 1)[1], materials.split("Dielectrics:\n", 1)[1]
    left = harness.cylinder_geo(.120, sides, a=.100, eps=2.8-.06j, center=(.031,-.017))
    right = harness.cylinder_geo(.092, sides, a=.073, eps=3.1-.085j, center=(.35,-.017))
    a, first = sections_and_material(left)
    b, second = sections_and_material(right)
    b = b.replace("coat_outer", "outer_right").replace("coat_inner", "inner_right").replace(" 0 1 0\n"," 0 2 0\n")
    return "Title: two coated PEC cylinders\n" + a + b + "IBCS_Resistances:\n\nDielectrics:\n" + first + "2 " + second.split(" ",1)[1]


def process_sample(pid):
    try:
        info = psutil.Process(pid).memory_info()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {}
    return {"rss_bytes": info.rss, "private_bytes": getattr(info, "private", None),
            "peak_working_set_bytes": getattr(info, "peak_wset", None),
            "peak_private_commit_bytes": getattr(info, "peak_pagefile", None)}


def worker(root, audit, run):
    os.environ["GRIM_ROOT"] = str(root)
    sys.path.insert(0, str(audit))
    import harness
    cfg = json.loads((run / "request.json").read_text())
    text = (run.parent / "geometry.geo").read_text(encoding="utf-8")
    angles = np.arange(-90., 90.) if cfg["angles"] == 180 else np.arange(360.)
    result = {"completed": False}
    started = time.perf_counter()
    try:
        solved, elapsed = harness.solve_fixed(text, cfg["ghz"], angles, "dense", threads=cfg["threads"],
                                              dense_residual_storage="auto")
        fields = harness.fields_of(solved)
        assert set(fields) == {"TE", "TM"}
        if any(f.shape != angles.shape or not np.isfinite(f).all() for f in fields.values()):
            raise ValueError("Field arrays have missing or non-finite values")
        np.savez_compressed(run / "fields.npz", angles=angles, **fields)
        meta = solved["metadata"]
        result.update(completed=True, solve_seconds=elapsed, facts=harness.facts(solved),
                      residual=meta.get("residual_norm_max"), unknowns=meta.get("dense_largest_system"), rhs_batches=meta.get("dense_rhs_batch_count"),
                      columns=meta.get("dense_rhs_column_count"), reuses=meta.get("assembled_system_reuses"),
                      ledger=meta.get("memory_accounting"), memory_estimates=(meta.get("experimental_cpu") or {}).get("memory_estimates"))
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=str(exc), diagnostics=getattr(exc,"solver_diagnostics",None))
        traceback.print_exc()
    result.update(worker_seconds=time.perf_counter()-started, end_process=process_sample(os.getpid()))
    dump(run / "result.json", result)
    return 0 if result.get("facts", {}).get("quality_passed") else 1


def run_one(root, audit, run, cfg, commit_reader):
    run.mkdir()
    dump(run / "request.json", cfg)
    env = dict(os.environ)
    for key in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        env[key] = str(cfg["threads"])
    cmd = [sys.executable, __file__, "--worker", str(root), str(audit), str(run)]
    start = time.perf_counter()
    with (run / "worker.log").open("w", encoding="utf-8") as log, (run / "samples.jsonl").open("w", encoding="utf-8") as samples:
        with subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT) as proc:
            try:
                while True:
                    row = dict(t=time.perf_counter()-start, available_ram_bytes=psutil.virtual_memory().available,
                               process=process_sample(proc.pid), system_commit=commit_reader())
                    samples.write(json.dumps(row)+"\n")
                    samples.flush()
                    if proc.poll() is not None:
                        break
                    time.sleep(.25)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait()
    resultfile = run / "result.json"
    result = json.loads(resultfile.read_text()) if resultfile.exists() else {"completed": False}
    observed = [json.loads(line) for line in (run / "samples.jsonl").read_text().splitlines()]
    counters = [r["process"] for r in observed] + [result.get("end_process", {})]
    commits = [r["system_commit"] for r in observed if r["system_commit"]]
    summary = {"exit_code": proc.returncode, "solve_seconds": result.get("solve_seconds"),
            "elapsed_seconds": time.perf_counter()-start, "completed": result["completed"],
            "quality_passed": result.get("facts",{}).get("quality_passed"), "residual": result.get("residual"),
            "rhs_batches": result.get("rhs_batches"), "error": result.get("error"),
            "peak_working_set_bytes": max((c["peak_working_set_bytes"] for c in counters if c.get("peak_working_set_bytes") is not None), default=None),
            "peak_private_commit_bytes": max((c["peak_private_commit_bytes"] for c in counters if c.get("peak_private_commit_bytes") is not None), default=None),
            "sampled_min_available_ram_bytes": min(r["available_ram_bytes"] for r in observed),
            "sampled_peak_system_commit_bytes": max((c["committed_bytes"] for c in commits), default=None),
            "sampled_min_system_commit_headroom_bytes": min((c["limit_bytes"]-c["committed_bytes"] for c in commits), default=None)}
    if sys.platform == "win32":
        summary["windows_counters_complete"] = all(summary[k] is not None for k in (
            "peak_working_set_bytes", "peak_private_commit_bytes", "sampled_peak_system_commit_bytes",
            "sampled_min_system_commit_headroom_bytes"))
    return summary


def compare_fields(first, second):
    if not (first / "fields.npz").exists() or not (second / "fields.npz").exists():
        return None
    with np.load(first / "fields.npz", allow_pickle=False) as a, np.load(second / "fields.npz", allow_pickle=False) as b:
        if not np.array_equal(a["angles"], b["angles"]):
            raise ValueError("Incident-angle mismatch")
        result = {}
        for pol in ("TE", "TM"):
            delta = float(np.abs(a[pol]-b[pol]).max())
            peak = float(np.abs(a[pol]).max())
            result[pol] = {"bit_identical": a[pol].tobytes()==b[pol].tobytes(), "max_abs_delta":delta,
                           "max_delta_over_shipped_peak": delta / peak if peak else None}
        return result


def main():
    if len(sys.argv) == 5 and sys.argv[1] == "--worker":
        return worker(*(Path(x) for x in sys.argv[2:]))
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("shipped","corrected","audit","output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--angles", nargs="+", type=int, choices=(180,360), default=[180,360])
    parser.add_argument("--geometry", type=Path, help="User geometry in metres; defaults to the mixed two-cylinder fixture")
    parser.add_argument("--sides", type=int, default=4224, help="Outer sides per cylinder of the default fixture")
    parser.add_argument("--ghz", type=float, default=10.)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=1, help="Use 2 to reverse the pair order at each angle count")
    parser.add_argument("--linux-smoke", action="store_true", help="Allow a Linux harness verification with unavailable Windows counters")
    args = parser.parse_args()
    if sys.platform != "win32" and not (sys.platform.startswith("linux") and args.linux_smoke):
        parser.error("Run on native Windows; --linux-smoke is only for testing this harness on Linux.")
    if args.repeats < 1 or args.threads < 1 or args.sides < 8 or args.ghz <= 0 or len(set(args.angles)) != len(args.angles):
        parser.error("Provide positive settings, at least eight sides and distinct angle counts.")
    roots = {"shipped":args.shipped.resolve(), "corrected":args.corrected.resolve()}
    check_sources(roots)
    audit = args.audit.resolve()
    os.environ["GRIM_ROOT"] = str(roots["shipped"])
    sys.path.insert(0, str(audit))
    import harness
    from ghost_backend.execution.memory import windows_system_commit
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    geo = args.geometry.read_text(encoding="utf-8-sig") if args.geometry else mixed_geometry(harness, args.sides)
    (out / "geometry.geo").write_text(geo, encoding="utf-8")
    dump(out / "host.json", {"platform":platform.platform(),"python":sys.version,"psutil":psutil.__version__,
                             "numpy":np.__version__, "physical_ram_bytes":psutil.virtual_memory().total,
                             "native_windows":sys.platform=="win32", "geometry_sha256":hashlib.sha256(geo.encode()).hexdigest(),
                             "sides":None if args.geometry else args.sides, "ghz":args.ghz, "threads":args.threads})
    report = {}
    good = True
    for rep in range(args.repeats):
        for idx, angles in enumerate(args.angles):
            case = f"r{rep+1}_a{angles}"
            order = list(reversed(roots)) if (rep+idx)%2 else list(roots)
            item = {"order":order}
            for variant in order:
                dest = out / (case+"_"+variant)
                item[variant] = run_one(roots[variant], audit, dest, dict(ghz=args.ghz, threads=args.threads, angles=angles), windows_system_commit)
                good = good and item[variant]["exit_code"]==0 and item[variant].get("windows_counters_complete",True)
            item["field_comparison"] = compare_fields(out/(case+"_shipped"), out/(case+"_corrected"))
            report[case] = item
            dump(out / "summary.json", report)
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
