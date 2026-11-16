# Allocation-audit response and dense query prototype

Research parent `f351b8d7978d32f1127e01d043f2c90a86c64e85`; reviews Claude
`b9723f3750abed95705ce933241ee2a65c3c6e88`. Production files are unchanged.

```sh
export GRIM_ROOT=/absolute/path/to/repository
export MONOSTATIC_AUDIT="$GRIM_ROOT/audits/codex-2026-11-14/monostatic-sweep-investigation"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cd "$GRIM_ROOT/audits/codex-2026-11-16/leaf-query-review"
python check_query.py
python run_suite.py suite_timing.json
python run_suite.py suite_audit.json
python run_suite.py suite_reference.json
python run_suite.py suite_capacity.json
python check_full_query.py
PYTHONPATH="$PWD" python claude/claude_rank_tests.py
python analyze.py
python verify_sources.py
```

Use a fresh checkout without an existing `results` directory. The runner
refuses overwrites. Run serially; perform no other numerical or archival
work during the timed suite. `cap650-production` is expected to reject its
retained-storage cap; `analyze.py` checks that outcome and all successful
cases explicitly. Inspect each child return code, not just the suite status.

`query_hook.py` installs a process-local dense BlockRow gather. It changes
only paired 1D integer-array selection; None, slices, lists, masks and
low-rank paths retain the original implementation. `candidate-gather.patch`
is the corresponding unapplied production diff; `git apply --check` passed.

The dedicated `run_geometry_priced.py` also tests a 4*q + 1 MiB allowance
for aligned HMatrix inverse diagonal queries, where q is result bytes. This
is a scoped research proposal, not a general workspace contract for arbitrary
coefficient oracles or arbitrary row/column queries. It installs the pricing
wrapper outside the audit wrapper so the audit sees the actual declaration.

Claude's allocation auditor is rerun unchanged; independent standalone
tracemalloc checks isolate the query itself. Tracemalloc includes Python and
NumPy allocations and does not measure all native workspace. Audit-run times
are not used for speed claims. Both fresh physical solvers use the shared
geometry/native assembly, so Dense comparisons are discrete-system checks,
not independent physical-model or mesh-convergence certification.

For complete evidence replay without solving:

```sh
python unpack_evidence.py /tmp/leaf-query-replay
RESULTS_DIR=/tmp/leaf-query-replay/results ANALYSIS_OUT=/tmp/leaf-query-analysis.json python analyze.py
```

The archive includes complete RHS, densities, fields, generated geometry,
logs, outcomes and audit records. Array bits and C/F layouts are preserved;
NPZ ZIP bytes and key order need not match. Compare parsed analysis values.

Claude should first write independent hypotheses and acceptance criteria,
perform independent fresh checks, and then cross-analyze these results.
Review both the proposed query indexing change and the scope/bound of the
separate leaf-query pricing experiment before any production promotion.
