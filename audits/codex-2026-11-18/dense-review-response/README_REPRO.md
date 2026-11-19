# Reproduce the Dense review response

Baseline `main`: `bf5201c26e0fa3ac98faf6363e52ab9e118d1a7c`.
Rejected NumPy-F candidate: `5542cd52969953b1e165c95109de35aa4dd75da8`.
Claude review: `df18342afb09cd6c6cd3b954c5ef1d8afb3b3894`.

This response branch has **no production changes**. `research/direct_blas_dense.py` is a complete replacement module for a disposable **baseline** checkout only. It is not a recommended distribution update. Prepare `DIRECT_GRIM_ROOT` by copying the baseline checkout and replacing `tools/GHOST/ghost_backend/linalg/dense.py` with that research file. Set `BASE_GRIM_ROOT` to the baseline checkout and `OLD_GRIM_ROOT` to the rejected candidate checkout. NumPy, SciPy and the repository dependencies are required.

Run scripts from a disposable copy of this audit directory. Use an empty `fresh/` directory: the suite runners refuse to overwrite results. The reviewer files can be fetched without Git history using `python download_claude.py`; each of its 414 pinned files is checked against its Git blob SHA. Run timed suites sequentially.

```sh
python download_claude.py
mkdir -p fresh
OPENBLAS_NUM_THREADS=4 python claude/bench/interleaved_bench.py 4146 fresh/claude-interleaved-t4.json
python run_clean_checks.py
python run_physical.py
python run_followup.py
OPENBLAS_NUM_THREADS=1 python check_direct.py "$DIRECT_GRIM_ROOT" check-direct.json
OPENBLAS_NUM_THREADS=1 python check_dense.py "$DIRECT_GRIM_ROOT" fresh/fallback-direct
OPENBLAS_NUM_THREADS=1 GRIM_ROOT="$BASE_GRIM_ROOT" python claude/dense_tree_test.py main fresh/synthetic-main
OPENBLAS_NUM_THREADS=1 GRIM_ROOT="$DIRECT_GRIM_ROOT" python claude/dense_tree_test.py direct fresh/synthetic-direct
python replay_claude.py
python analyze.py
```

`interleaved_check.py` reads actual NumPy and SciPy pool sizes using GHOST's bundled `ThreadpoolController` (or installed threadpoolctl). It applies limits separately by library path. The clean controls validate answers with elementwise reductions outside timing, avoiding a new BLAS call between sweeps. Five randomized repetitions measure each variant in each process. The initial eight exploratory pool cases used `interleaved_check_initial.py`, whose validation used `np.linalg.norm` between sweeps. Those records are retained and labeled exploratory, not used for the headline clean comparisons. To reproduce them, run `run_checks.py`, which uses `interleaved_check_initial.py`; do not mix their results with the clean controls. Eight threads exceed this host's four-CPU quota and are an oversubscription probe, not evidence about an eight-core desktop.

The original 820-case reviewer test prints `patched=False` for the direct-BLAS candidate: that marker only searches for the rejected NumPy-F expression. The actual source identities are in `source-provenance.json`; the direct path is separately exercised by 30 dispatch checks.

Physical runs use the real geometry API and its residual/condition gates, 180 monostatic angles, the shared partial-coating fixture at 5 GHz, 0.6 m nominal diameter, relative permittivity 12-0.01j, and P1 discretization. The resulting system has 4,146 unknowns. Measured solve times exclude the wrapper's pool observation and evidence copy, while overall wall time includes them. The wrappers do not change numerical options or tolerances. Pool sizes are read inside every measured solve. The same fixture is intentional reproduction, not an independently derived physical reference model.

## Replay only

```sh
python evidence.py unpack /tmp/dense-response-replay
FRESH_DIR=/tmp/dense-response-replay/fresh ANALYSIS_OUT=/tmp/dense-response-analysis.json python analyze.py
```

The archive holds every fresh process record, every physical complex field at all 180 angles, the first up to 16 RHS/density columns of every physical run, all 820 solutions from each of the two synthetic-suite runs, the fallback-suite solutions, and limited expression-benchmark snapshots (first RHS, first up to four columns, first repetition). All full benchmark answers were checked when computed; the archive does not retain every transient timing-loop answer. Archive parts and extracted members are SHA-256 checked. Reviewer field cross-analysis uses the separately downloaded pinned `claude/` directory; it does not execute a solve.

Neither Windows, a second BLAS build, near-full 32 GB memory pressure, nor an end-to-end default-thread policy change is validated here. No native DLL/.so was rebuilt. All research code remains outside production.
