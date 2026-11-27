"""Study C driver: each job in a fresh process, backends interleaved, nothing else running.

    GRIM_ROOT=<ed90b65> python study_c_timing.py results/c "<sides>:<angles>:<threads>:<repeats>[:ghz]" ...
"""
import json, os, subprocess, sys, time
from pathlib import Path

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
here = Path(__file__).resolve().parent
log = out / "runs.jsonl"
for spec in sys.argv[2:]:
    parts = spec.split(":")
    sides, angles, threads, repeats = (int(x) for x in parts[:4])
    ghz = parts[4] if len(parts) > 4 else "10"
    for repeat in range(repeats):
        for backend in (("dense", "compressed") if repeat % 2 == 0 else ("compressed", "dense")):
            tag = f"s{sides}_a{angles}_t{threads}_f{ghz}_{backend}_r{repeat}"
            env = dict(os.environ, PYTHONPATH=str(here))
            t = time.perf_counter()
            proc = subprocess.Popen([sys.executable, str(here / "timed_job.py"), str(sides), backend, str(angles),
                                     str(threads), str(out / f"{tag}.npz"), ghz],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
            stdout, stderr = proc.communicate()
            _, status, usage = os.wait4(proc.pid, os.WNOHANG) if False else (None, proc.returncode, None)
            row = dict(tag=tag, repeat=repeat, returncode=proc.returncode, launcher_wall_s=round(time.perf_counter() - t, 3))
            try:
                row.update(json.loads(stdout.strip().splitlines()[-1]))
            except Exception:
                row["stderr_tail"] = stderr[-600:]
            with log.open("a") as f:
                f.write(json.dumps(row, default=str) + "\n")
            print(tag, row.get("linear_backend"), row.get("unknowns_per_system"), row.get("solve_wall_s"),
                  row.get("peak_rss_gib"), row.get("stderr_tail", "")[-200:], flush=True)
