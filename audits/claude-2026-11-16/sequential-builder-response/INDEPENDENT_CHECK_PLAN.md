# Independent check plan (written before running anything for this round)

Reviewing Codex `f351b8d` (`sequential-builder-review/REVIEW_AND_HANDOFF.md`).
Read so far: that document, `PLAN.md`, `README_REPRO.md`. Not yet opened:
Codex's corrected builder, its instrumentation, or any result file.

## What I expect to be true before measuring

1. Child-solve scratch. Codex says my 1 MiB allowance is too small. Reading
   the production `solve_into`: each level computes `z -= e @ correction`,
   which allocates a temporary the size of that half of the right-hand side.
   For a child solve applied to `u` (n/2 rows), the largest temporary is about
   half of `u.nbytes`. So I expect Codex to be right and my allowance wrong by
   a large factor on real cases (root `u` is about 12.7 MiB on the multilayer).
   I also expect production's `8*u.nbytes + 1 MiB` to be conservative by
   roughly an order of magnitude.
   Test: trace NumPy allocations during the real aliased root solves.
   Accept Codex's finding if measured scratch exceeds 1 MiB.
2. Woodbury matrix not carried as live. Expected true from my own source: I
   create `small` in one guard and use it in a later one without passing it.
3. Refinement counter is cumulative over condition probes and field solves.
   Expected true; I never checked. Test with my own per-call wrapper.
4. Condition estimate uses normal and adjoint only. Check by recording the
   `trans` argument of every inverse call in a production run.

## Independent audit of "is the accounting now conservative?"

Not a re-run of Codex's checks. My own instrument: trace NumPy allocations for
the whole inverse build and, at every construction guard entry, compare
- accounted = retained bytes + declared live + declared additional, with
- actual = traced bytes live at entry plus the peak growth inside the guard,
both relative to the start of the build.
Report, for production build, my original sequential build, and Codex's
corrected sequential build (packed and unpacked): number of guard entries
where actual exceeds accounted, and the largest shortfall.
Acceptance for "conservative": zero shortfalls above 1 MiB. Limitation known
in advance: tracemalloc sees NumPy buffers, not LAPACK/BLAS internal scratch,
so this can find under-accounting but cannot prove its absence.
Prediction: production has no shortfalls; my original has shortfalls of
several MiB at the in-place solves; Codex's corrected copy has none.

## Rank-direction guard

Own unit tests on Codex's `rank_guard` (written before reading its tests):
e-type array with one tiny column, v-type with one tiny row, both with
compensating partners; an array that is fine by direction but would fail a
naive check in the other direction; all-zero rank vector; and the 17 earlier
cases. Physical: confirm retained inverse bytes are unchanged by the rank
guard on multilayer TM and partial TE (benefit preserved).

## Per-call refinement and tolerance

Own wrapper recording each inverse call (phase, trans, width, corrections).
Reproduce on multilayer TM at 1e-8 and 1e-10; add partial TE and TM as second
and third cases, which Codex did not scan. Report corrections, inverse size
and time by phase. No default recommended from single runs.

## End-to-end benefit of the sequential order (Codex's last question)

Choose a cap between the two unpacked thresholds (674 and 710 MiB), where
production must fall back to its smaller retry inverse and the sequential
build is clean. Paired, order-alternated, two runs each. Compare total wall
time and field-solve corrections. Accept "measured benefit" only if both
sequential runs beat both production runs by more than the spread.
