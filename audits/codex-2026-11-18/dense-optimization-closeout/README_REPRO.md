# Reproduce this bounded review

No production files are changed. Claude evidence is pinned to `4efea5f0579cff2e4907c4a88aa4118408c87fb7`; runtime baseline is main `bf5201c26e0fa3ac98faf6363e52ab9e118d1a7c`.

Run from a copy of this directory with NumPy and SciPy installed. Set `GRIM_ROOT` to a baseline checkout. The bundled GHOST threadpool controller is used; no separate threadpoolctl installation is required.

```sh
python download_claude.py
OPENBLAS_NUM_THREADS=1 python replay.py
OPENBLAS_NUM_THREADS=1 python claude/bench/pool_controls.py 4146 4 4 new-pools-4-4.json
OPENBLAS_NUM_THREADS=1 python claude/bench/pool_controls.py 4146 1 4 new-pools-1-4.json
```

Run timing commands sequentially. They use the reviewer's unmodified script, not a new solver implementation. Each pool combination is one process with six alternating repetitions of nine solver/product combinations. The script saves medians, not individual repetitions. The explicit-inverse multiply is a routing control, not a proposed production inverse. The computed correction is not applied to the solution; this is a call-sequence benchmark, not a refinement-accuracy test.

`replay.py` checks 28 saved Dense runs, all published 180-angle fields against corresponding main runs, three full density arrays and their hashes, and six operator-storage records (including the disclosed condition-gate failure). It checks the other five Compressed fields for shape/finiteness, not against independent analytical or Dense anchors. Fresh physical solves and synthetic suites were not repeated this round. No Windows tests were performed.

All 157 reviewer files are included unchanged under `claude/` and individually checked against their Git blob identities in `claude-inventory.json`. `download_claude.py` is also provided for independent retrieval. `PLAN.md` records the limited validation scope chosen before these fresh runs.
