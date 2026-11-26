# Nested-cgroup RAM admission (handoff item 3)

Release under test: `ed90b65`, `tools/GHOST/ghost_backend/twod/solver.py` blob `8e15267c`.
Host: Linux, cgroup v1 memory controller (hybrid layout), Python 3.13.18, root.

| File | What it is |
|---|---|
| `codex-replay/` | Codex's two deterministic controls rerun unmodified; byte-identical to its shipped JSON |
| `fake_fs_cases.py` | Independent 14-case fake-filesystem harness (v2, v1, hybrid, rooted mounts, controls) driving the production probe and ledger |
| `fake_fs_release.json` / `fake_fs_fixed.json` | Its output for the release (9 of 14 wrong) and the patched copy (0 wrong, asserted) |
| `real_probe.py`, `run_real_cgroup.sh` | Real cgroups: a 1 GiB child, an unlimited grandchild, and two bind-mount layouts, created under this container's own memory group and removed afterwards |
| `real-cgroup/`, `real-cgroup-summary.txt` | Results for release and patched copy |
| `nested-cgroup-fix.patch` | Trial fix against `ed90b65` (not applied to the repo) |

Reproduce (root, cgroup v1 memory controller writable):

    python fake_fs_cases.py $GRIM/tools/GHOST observe
    python fake_fs_cases.py $FIXED/tools/GHOST assert-correct
    ./run_real_cgroup.sh $GRIM/tools/GHOST $FIXED/tools/GHOST real-cgroup

`$FIXED` is a checkout of `ed90b65` with the patch applied (`git apply nested-cgroup-fix.patch`).
