"""Report what the GHOST memory probe and request ledger see from inside the
cgroup this process is really in.  No fakes: real /proc and /sys/fs/cgroup.

Usage: python real_probe.py GHOST_ROOT LABEL [--assert-correct]

"levels" is this script's own walk of the real memory hierarchy (leaf to mount
point) and "true_remaining_bytes" is min(MemAvailable, min over finite levels
of limit - usage).  Usage moves between reads, so --assert-correct allows
64 MiB between that and the probe.  Allocates nothing beyond the imports.
"""
import json, os, sys
root, label = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
GIB = 2**30


def read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError as e:
        return None


def walk():
    member = {}
    for line in open("/proc/self/cgroup"):
        i, ctrl, path = line.rstrip("\n").split(":", 2)
        if i == "0" and ctrl == "":
            member["cgroup2"] = path
        if "memory" in ctrl.split(","):
            member["cgroup"] = path
    hierarchies = []
    for line in open("/proc/self/mountinfo"):
        left, _, right = line.partition(" - ")
        f, t = left.split(), right.split()
        if t[0] == "cgroup2":
            names = ("memory.max", "memory.current")
        elif t[0] == "cgroup" and "memory" in t[2].split(","):
            names = ("memory.limit_in_bytes", "memory.usage_in_bytes")
        else:
            continue
        group = member.get(t[0])
        mroot, mp = f[3], f[4]
        if group is None:
            continue
        rel = group[len(mroot.rstrip("/")):] if (group + "/").startswith(mroot.rstrip("/") + "/") else ""
        parts = [p for p in rel.split("/") if p]
        levels = []
        for n in range(len(parts), -1, -1):
            d = "/".join([mp] + parts[:n])
            lim, use = read(d + "/" + names[0]), read(d + "/" + names[1])
            finite = lim is not None and lim.isdigit() and int(lim) < 2**60
            levels.append(dict(dir=d, limit=lim, usage=use,
                               remaining_bytes=int(lim) - int(use) if finite and use and use.isdigit() else None))
        hierarchies.append(dict(fstype=t[0], mount_root=mroot, mount_point=mp, process_group=group, levels=levels))
    return hierarchies


mem_available = [int(l.split()[1]) * 1024 for l in open("/proc/meminfo") if l.startswith("MemAvailable:")][0]
before = walk()
from ghost_backend.twod import solver
from ghost_backend.execution.memory_budget import MemoryBudget
cg = solver._cgroup_available_bytes()
detected = solver._detect_available_gb()
os.environ.pop("GHOST_MAX_SOLVE_GB", None)
ledger = MemoryBudget()
budget = ledger.limit()
levels = [l["remaining_bytes"] for h in walk() for l in h["levels"] if l["remaining_bytes"] is not None]
true = min([mem_available] + levels)
row = dict(label=label, ghost_root=root, proc_self_cgroup=open("/proc/self/cgroup").read(),
           hierarchies=before, mem_available_bytes=mem_available,
           true_remaining_bytes=true, true_remaining_gib=true / GIB,
           probe_cgroup_remaining_bytes=cg, probe_detected_available_gib=detected,
           correct_budget_gib=0.9 * true / GIB, ledger_budget_gib=budget,
           ledger_binding=ledger.last.get("binding_constraint"),
           over_admitted_gib=budget - 0.9 * true / GIB)
print(json.dumps(row, indent=1))
if "--assert-correct" in sys.argv and abs(detected * GIB - true) > 64 * 2**20:
    sys.exit("WRONG: detected %.3f GiB, true %.3f GiB" % (detected, true / GIB))
