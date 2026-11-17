# Reproduce the integrated HMatrix candidate

Baseline production: `5fec63200d48d6dd7536221d992b3e1836a1647c`.
The publication parent `c536f7e7ab5dc12692e02c0035d3ad653299905f` has identical
production files. Use this branch for the candidate checkout.

```sh
export GRIM_ROOT=/absolute/path/to/candidate
export BASE_GRIM_ROOT=/absolute/path/to/baseline
export MONOSTATIC_AUDIT="$GRIM_ROOT/audits/codex-2026-11-14/monostatic-sweep-investigation"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cd "$GRIM_ROOT/audits/codex-2026-11-17/hmatrix-production-integration"
python test_gather.py
python test_build.py
python run_suite.py suite_physical.json
python check_diagonal.py diagonal-allocation.json
python run_suite.py suite_performance.json
python run_suite.py suite_cancel_followup.json
python check_gather_allocation.py
python analyze.py
```

For fresh solves, use a disposable audit copy with no `results/` directory.
The suite refuses overwrites once a case has a return-code record. Runs are
serial fresh processes, and the 32k pair takes substantially longer than the
small physical suite. Do not run memory-intensive checks concurrently with
timing cases. RAM budgets here are test settings, not changes to product limits.

The suite loads actual baseline/candidate production code. It installs no
gather/build-order research hook. Its wrappers trace allocations, workers and
build tolerances or inject named cancellation/compression failures. The PEC
case exercises the native TM single-layer path, not the full GUI's combined
closed-boundary route. Every solve has 180 monostatic angles and saved full
density/RHS/field arrays. No mesh certificate is implied.

The first product-cancel case permits cancellation at an idle checkpoint.
The separate followup requires a task in flight; both raw outcomes are retained.
No timing claim uses cancellation or fault-injection cases.

Replay the published evidence without solving:

```sh
python unpack_evidence.py /tmp/hmatrix-integration-replay
RESULTS_DIR=/tmp/hmatrix-integration-replay/results ANALYSIS_OUT=/tmp/hmatrix-integration-analysis.json python analyze.py
```

The archive manifest checks all part/payload hashes. NPZ container bytes may
change on reconstruction; numerical array bits and C/F layouts are preserved.
`evidence-verification.json` records comparison with the original results.
`production-change.patch` shows the three-file production diff; native libraries
and the earlier inverse-upgrade repair remain unchanged.

The focused builder tests use synthetic matrices and controlled rejection to
check lifecycle/accounting; the separate native suite supplies physical-system
algebraic and field comparisons. Timings exclude exact-row validation and
archive writing. The analysis keeps matched-policy comparisons separate from
the capped pair, where the admitted inverse tolerance may differ.
