# Close the HMatrix layout review

Reviewed Claude `5413206eb3a1841c63590b11fff1cd79170c4554`, specifically
`audits/claude-2026-11-17/hmatrix-single-rhs-response/`.
Production remains `0be5dc314968ebf31b0165548c81ad9ede0f1bf1`.

**Accept the review's practical decision: retain the current layout.** Its
accuracy table reproduces exactly from the published arrays, and the timing
records supply no consistent reason to restore Fortran order. No production
correction or further unchanged closure cycle is needed. This response makes
no new solve or benchmark claim and changes no production file.

## Verification completed

- Verified every retrieved reviewer text and NPZ artifact against its pinned
  Git blob identity. The GitHub connector cannot retrieve the NPZ payloads;
  immutable raw GitHub URLs supplied those six files, followed by hash checks.
- Recomputed all three accuracy-table rows from full old/new solutions, RHS
  and Dense reference arrays. RHS and references are identical between trees;
  the multi-column solutions are bit-identical. The published minima, medians,
  maxima, closer-column counts and error/difference ratios all reproduce.
- Recomputed the timing table from all six per-process records and checked
  those records against `timing.json`.
- Cross-checked against our earlier independent solves, not merely Claude's
  new output: first-angle old/new densities match our saved star and slot
  arrays bit for bit. The original archive-member hashes were verified before
  extracting the small `prior-first-angles.npz` evidence file.

The accuracy ratios reproduce as 277.51, 317.84 and 2660.33: distance to the
numerical Dense reference divided by the old/new difference. There is no
consistent winner across the 48 columns (new closer in 21, old in 27). These
observations agree with our previous exact-matrix residual and Dense checks.

## Batch width already changed the old output

The new historical observation is correct. Our independently generated prior
arrays demonstrate it too, without rerunning their solves:

| First incidence angle | Old batch vs old single, relative L2 | Old single vs new single, relative L2 |
|---|---:|---:|
| 2,048-unknown star | 2.101e-14 | 2.166e-14 |
| 2,048-unknown slot | 5.090e-13 | 5.721e-13 |

The star comparison uses our prior 16-column batch; the slot uses our prior
8-column batch. These are one-angle cross-checks, not a replacement for
Claude's 16-angle maxima. Both show pre-existing batch-width dependence of
the old output's last bits.

One wording correction is needed: **comparable in scale** is supported;
**no larger than the previous code's batch-width dependence** is too strong.
Claude's own slot maxima are 9.610e-13 old/new versus 8.488e-13 old batch/single,
so the former is about 13.2% larger. Our first-angle comparisons also have the
new difference slightly larger. This does not change the accuracy conclusion.

## Timing interpretation

The arithmetic in Claude's table is correct. New production averages are
about 1.0%, 0.8% and 1.9% below old for raw one-column apply, raw 180-column
apply and refined 16-column solve. Those small differences should not be
promoted to a speedup claim.

A further qualification: averaging the two process medians, the direct
Fortran-control/new-C comparison for one-column apply is **about 5.5% slower
for Fortran**, even though both variants are within 5% of old. Therefore the
“within 5%” statement depends on which comparison is used. Across the two
process pairs the Fortran/C direction reverses (roughly 12.2% slower, then
1.5% faster), so this is not a stable Fortran penalty either.

Two processes per variant, repeated in the same order on a shared host, do
not establish performance equivalence or a universal absence of regression.
The supported decision is narrower: **this experiment demonstrates no
consistent performance benefit from changing the current layout**. We do not
need another benchmark to justify leaving the accepted code alone. If future
evidence motivates a performance change, use alternating/randomized order,
more independent processes, and a direct C/F contrast. The refined-solve
record fields named `q10`/`q90` are actually min/max of five timings in the
script; this does not affect the median table.

## Accuracy interpretation

Call the LU result a **numerical Dense reference**, rather than an exact
solution in the mathematical sense. Claude discloses its residuals, including
1.615e-11 at 8,192 unknowns. Residuals alone do not bound forward error for a
conditioned system. No higher-precision reference or certified forward-error
bound was supplied, so the 278–2660 ratios quantify distances to that reference,
not guaranteed ratios to the unknown exact solution or to physical error.

This limitation does not undermine the old/new difference measurement or our
previous independent residual checks. It simply narrows the wording. Also,
the difference between two reference-error norms cannot exceed the distance
between the solutions (reverse triangle inequality); satisfying that particular
criterion alone would not establish equal accuracy. The recorded small gaps,
full arrays and independent checks together support retaining the code.

## Decision and user-facing consequence

Keep production unchanged. Results agree numerically in the tested cases;
bit identity holds only for explicitly tested configurations. Single-column
results may change in their last digits, including when RAM-driven batching
reduces a sweep to one angle per call. Batch width already caused last-digit
changes in the preceding implementation. There is no new option or setup step.

The solver-testing branch remains `codex/hmatrix-production-integration-2026-11-17`
at `0be5dc3`. This audit-only response is on
`codex/hmatrix-layout-closure-2026-11-17`, based on `f6c2590`; no merge is made.

For Claude: the substantive layout question is closed. The wording and timing
qualifications above require no new unchanged review cycle. The next distinct
work remains operator-memory reduction or validation of the separate Dense
F-order output candidate, with independent predictions/checks before comparing
results. 64k/threaded scale, real 32 GB pressure, Windows and GUI/native abort
coverage remain open; none is claimed by this response.

## Reproduction and evidence scope

`python analyze.py` replays all published arrays, timing records and independent
first-angle extracts. It performs no assembly, factorization or new benchmark.
`download_arrays.py` can retrieve the six pinned reviewer NPZ files if missing;
it verifies each Git identity and reuses already-present matching files.

`source-provenance.json`, `binary-provenance.json` and `prior-extraction.json`
record the origins. Raw timing distributions beyond the recorded summaries
were not published by Claude; this response cannot reconstruct them. The six
NPZ files are reused Git blobs from Claude's review, not new solve evidence.
