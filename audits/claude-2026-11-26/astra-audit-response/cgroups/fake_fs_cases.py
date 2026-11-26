"""Independent fake-filesystem cases for the GHOST Linux memory probe.

Usage: python fake_fs_cases.py GHOST_ROOT {observe|assert-correct} > out.json

GHOST_ROOT is a tools/GHOST directory (the release, or a patched copy).
The whole production module and the production MemoryBudget ledger run; only
`open` inside ghost_backend.twod.solver, the host-availability probe (fixed
at 24 GiB) and the RSS probe (0.25 GiB) are replaced.  No memory is allocated.
"observe" records what the probe returns.  "assert-correct" additionally
fails unless every case returns the true headroom and 0.9 x that budget.
True headroom = min(host available, min over the process's group and every
ancestor with a finite limit of limit - usage).
"""
import builtins, io, json, os, sys
from unittest.mock import patch

root, mode = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
from ghost_backend.twod import solver
from ghost_backend.execution.memory_budget import MemoryBudget

GIB = 2**30
HOST = 24 * GIB
RSS = GIB // 4
V1_UNLIMITED = 9223372036854771712   # what this kernel reports for "no limit"
V2 = "{id} {par} 0:28 {root} {mp} rw,nosuid - cgroup2 cgroup2 rw\n"
V1 = "{id} {par} 0:32 {root} {mp} rw,relatime - cgroup cgroup rw,memory\n"
V1CPU = "37 36 0:29 / /sys/fs/cgroup/cpu rw,relatime - cgroup cgroup rw,cpu\n"


def v2(mount, groups):
    return {mount + g + "/" + n: str(v) + "\n" for g, (lim, use) in groups.items()
            for n, v in (("memory.max", lim), ("memory.current", use)) if v is not None}


def v1(mount, groups):
    return {mount + g + "/" + n: str(v) + "\n" for g, (lim, use) in groups.items()
            for n, v in (("memory.limit_in_bytes", lim), ("memory.usage_in_bytes", use)) if v is not None}


C = "/sys/fs/cgroup"
CASES = [
 dict(name="A v2 root control: process at mount root, finite root limit", true=1.0,
      cgroup="0::/\n", mounts=V2.format(id=32, par=31, root="/", mp=C),
      files=v2(C, {"": (2*GIB, GIB)})),
 dict(name="B v2 nested: unlimited root, tight leaf", true=1.0,
      cgroup="0::/job\n", mounts=V2.format(id=32, par=31, root="/", mp=C),
      files=v2(C, {"": ("max", 8*GIB), "/job": (2*GIB, GIB)})),
 dict(name="C v2 finite ancestor, leaf 'max', loose finite root", true=1.0,
      cgroup="0::/job/worker\n", mounts=V2.format(id=32, par=31, root="/", mp=C),
      files=v2(C, {"": (32*GIB, 8*GIB), "/job": (2*GIB, GIB), "/job/worker": ("max", GIB//4)})),
 dict(name="D v2 mount rooted below the global hierarchy; tighter child of the mount root", true=1.0,
      cgroup="0::/kubepods/pod1/ctr\n", mounts=V2.format(id=32, par=31, root="/kubepods/pod1", mp=C),
      files=v2(C, {"": (8*GIB, 2*GIB), "/ctr": (3*GIB, 2*GIB)})),
 dict(name="E v1 nested (this container's layout): unlimited root, tight leaf", true=1.0,
      cgroup="4:memory:/process_api/id/claude-code-bash\n1:cpu:/\n0::/\n",
      mounts=V1CPU + V1.format(id=40, par=36, root="/", mp=C + "/memory"),
      files=v1(C + "/memory", {"": (V1_UNLIMITED, 8*GIB), "/process_api": (V1_UNLIMITED, 2*GIB),
            "/process_api/id": (V1_UNLIMITED, 2*GIB), "/process_api/id/claude-code-bash": (2*GIB, GIB)})),
 dict(name="F v1 finite ancestor, unlimited leaf", true=1.0,
      cgroup="4:memory:/job/worker\n0::/\n", mounts=V1.format(id=40, par=36, root="/", mp=C + "/memory"),
      files=v1(C + "/memory", {"": (V1_UNLIMITED, 8*GIB), "/job": (2*GIB, GIB), "/job/worker": (V1_UNLIMITED, GIB//4)})),
 dict(name="G hybrid: v1 memory nested and tight, v2 mounted at /unified without memory files", true=1.0,
      cgroup="4:memory:/svc/job\n0::/svc/job\n",
      mounts=V1.format(id=40, par=36, root="/", mp=C + "/memory") + V2.format(id=46, par=36, root="/", mp=C + "/unified"),
      files=v1(C + "/memory", {"": (V1_UNLIMITED, 8*GIB), "/svc": (V1_UNLIMITED, 2*GIB), "/svc/job": (2*GIB, GIB)})),
 dict(name="H v1 container: mount root equals the process group (root != '/')", true=1.0,
      cgroup="4:memory:/docker/abc\n", mounts=V1.format(id=40, par=36, root="/docker/abc", mp=C + "/memory"),
      files=v1(C + "/memory", {"": (2*GIB, GIB)})),
 dict(name="I v1 container with a tighter sub-group below a mount rooted at /docker/abc", true=0.5,
      cgroup="4:memory:/docker/abc/sub\n", mounts=V1.format(id=40, par=36, root="/docker/abc", mp=C + "/memory"),
      files=v1(C + "/memory", {"": (4*GIB, GIB), "/sub": (GIB, GIB//2)})),
 dict(name="J v2 nested limit, usage counter unreadable (falls back to process RSS)", true=1.75,
      cgroup="0::/job\n", mounts=V2.format(id=32, par=31, root="/", mp=C),
      files=v2(C, {"": ("max", 8*GIB), "/job": (2*GIB, None)})),
 dict(name="K both tight: root is tighter than leaf (root must still win)", true=0.5,
      cgroup="0::/job\n", mounts=V2.format(id=32, par=31, root="/", mp=C),
      files=v2(C, {"": (4*GIB, 3*GIB + GIB//2), "/job": (2*GIB, GIB)})),
 dict(name="L no cgroup limit anywhere: host probe is the bound", true=24.0,
      cgroup="0::/job\n", mounts=V2.format(id=32, par=31, root="/", mp=C),
      files=v2(C, {"": ("max", 8*GIB), "/job": ("max", GIB)})),
 dict(name="M mount path containing an escaped space (\\040)", true=1.0,
      cgroup="0::/job\n", mounts=V2.format(id=32, par=31, root="/", mp="/mnt/cg\\040two"),
      files=v2("/mnt/cg two", {"": ("max", 8*GIB), "/job": (2*GIB, GIB)})),
 dict(name="N /proc unreadable: conventional root files still honoured", true=1.0,
      cgroup=None, mounts=None, files=v2(C, {"": (2*GIB, GIB)})),
]

real_open = builtins.open
out, failures = [], []
for case in CASES:
    files = dict(case["files"])
    if case["cgroup"] is not None:
        files["/proc/self/cgroup"] = case["cgroup"]
        files["/proc/self/mountinfo"] = case["mounts"]
    reads = []

    def fake_open(path, *a, **k):
        text = os.fspath(path) if not isinstance(path, int) else path
        if isinstance(text, str) and (text.startswith(("/proc/", "/sys/", "/mnt/cg"))):
            reads.append(text)
            if text not in files:
                raise FileNotFoundError(text)
            return io.StringIO(files[text])
        return real_open(path, *a, **k)

    with patch.dict(os.environ, {}, clear=True), \
         patch.object(solver, "open", fake_open, create=True), \
         patch.object(solver, "_psutil_available_bytes", return_value=HOST), \
         patch.object(solver, "_slurm_available_bytes", return_value=None), \
         patch.object(solver, "_process_rss_bytes", return_value=RSS):
        cg = solver._cgroup_available_bytes()
        detected = solver._detect_available_gb()
        ledger = MemoryBudget()
        budget = ledger.limit()
    row = dict(case=case["name"], true_remaining_gib=case["true"],
               probe_cgroup_remaining_gib=None if cg is None else cg / GIB,
               probe_detected_available_gib=detected,
               correct_budget_gib=0.9 * case["true"], ledger_budget_gib=budget,
               ledger_binding=ledger.last.get("binding_constraint"),
               over_admitted_gib=budget - 0.9 * case["true"], paths_read=reads)
    out.append(row)
    if abs(detected - case["true"]) > 1e-9 or abs(budget - 0.9 * case["true"]) > 1e-9:
        failures.append(case["name"])

print(json.dumps(dict(ghost_root=root, mode=mode, wrong_cases=failures, cases=out), indent=1))
if mode == "assert-correct" and failures:
    sys.exit("WRONG BUDGET: " + "; ".join(failures))
