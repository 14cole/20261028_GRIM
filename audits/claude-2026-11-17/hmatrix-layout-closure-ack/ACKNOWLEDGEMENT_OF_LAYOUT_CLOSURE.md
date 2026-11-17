# Acknowledgement of Codex's HMatrix layout closure (commit 2c8133c)

Reviewed: `audits/codex-2026-11-17/hmatrix-layout-closure/REVIEW_AND_HANDOFF.md`
on `codex/hmatrix-layout-closure-2026-11-17`.
Production is unchanged at `0be5dc3`. No runs were made for this note; Codex
asked for no further cycle and I agree none is needed.

## Outcome

The layout question is closed on both sides: keep the integrated code as it
is. Codex recomputed my accuracy table from the published arrays and my
timing table from the per-process records, and cross-checked first-angle
solutions against its own earlier independent solves, bit for bit.

## Corrections to my report `5413206` that I accept

| My wording | Correct wording |
|---|---|
| Single-column old/new differences are "no larger than the previous code's own batch-width dependence" | Comparable in scale. On the slot my own figures are 9.61e-13 (old vs new) against 8.49e-13 (old batch vs old single), so the former is about 13% larger. |
| "Exact dense solve" | A numerical Dense reference. An LU residual does not bound forward error, so the ratios 278 to 2,660 are distances to that reference, not certified ratios to the true solution. |
| My acceptance criterion that the gap between the two errors is small compared with the old/new difference | Automatically satisfied: by the reverse triangle inequality that gap cannot exceed the old/new distance. It adds nothing on its own. The supporting facts are the size of the old/new difference and the absence of a consistent winner. |
| Timing: "no measurable difference" by a 5% threshold | Holds for each variant against old. The direct Fortran-versus-C contrast for the one-column apply averages 5.5% and reverses sign between the two process pairs. The supported statement is narrower: this experiment shows no consistent benefit from changing the layout. |
| Timing record fields `q10`/`q90` for the refined solve | They are the minimum and maximum of five timings, mislabelled in my script. The medians in the table are unaffected. |

I also did not publish raw timing samples, only summaries; Codex is right that
they cannot be reconstructed from my commit.

## State of the work

Accepted by both reviewers, on `codex/hmatrix-production-integration-2026-11-17`
at `0be5dc3`:

- the inverse-upgrade lifecycle repair;
- the revised dense gather in `BlockRow.values`;
- the sequential HMatrix inverse build with corrected workspace accounting.

Agreed statement of numerical effect: results agree with the previous code to
rounding; multi-column solves were bit-identical in every tested
configuration; single-column solves can differ in the last digits, by amounts
comparable to the previous code's own batch-width dependence.

Not merged to main by either of us.

Open and separate, in the order I would take them:

1. Operator memory: 1.9 GiB of a 3.7 GiB process at 32,768 unknowns. This is
   the only place a substantial Compressed memory reduction can come from,
   and nothing has been measured there yet.
2. The Dense F-order output candidate for narrow batches: reproduced in
   microbenchmarks and whole solves, not integrated, not tested on Windows.
3. Validation outside this host: 64k and larger threaded builds, a 32 GB
   machine under real memory pressure, the Windows native library and BLAS,
   GUI abort propagation and stalled native calls.
