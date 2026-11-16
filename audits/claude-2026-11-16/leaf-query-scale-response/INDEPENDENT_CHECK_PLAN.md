# Independent check plan (written before running anything for this round)

Reviewing Codex `9da795e` (`leaf-query-scale-review/REVIEW_AND_HANDOFF.md`).
Read so far: that document only. Not opened: Codex's v2 patch, scripts, or
results.

## Points against my last report, and what I expect

1. Evidence gap: I wrote that fields were published; for the two 32k runs
   they were not (the star harness stores them inside its batch file, which my
   copy step skipped). Expected true. Fix: publish fields, exact-row
   residuals and array hashes for both runs, and a command that checks the
   density against the 32k density parts I published earlier.
2. Arithmetic: "about 1.7q" for the multilayer query should be 3.43q.
   Expected true: 1.16 MiB over q = 0.339 MiB.
3. Gather v1 is not exception-equivalent when one selector is empty and the
   other invalid. Expected true: `np.ix_` with an empty axis never touches the
   other axis's bounds. My tests compared out-of-range only with non-empty
   partners.

## Fresh checks

A. Gather v2 (own tests, before reading Codex's): everything from my previous
   script, plus empty-with-invalid in both orders, empty-with-valid, both
   empty, NaN payloads, signed zeros and infinities compared as raw bytes.
   Acceptance: identical bytes, dtype, shape, and identical exception type in
   every case.

B. Aligned-diagonal workspace claim. Codex argues from the partition that
   far blocks do not contribute to an ordinary leaf's diagonal query and that
   in a fallback subtree contributing rows are smaller than the query, so 4q
   covers modelled buffers. My check is empirical, on real assembled
   operators rather than a partition model: for every aligned diagonal
   subtree up to side 1,024, run the actual query under allocation tracing
   (with the v2 gather) and record peak / q and the number of low-rank rows
   that contributed. Geometries: dielectric star at 8,192 unknowns and a thin
   slot at 1,024 (a deliberately awkward near-field case).
   My own bound before measuring: result q, plus for a dense row covering the
   query 3 more chunks of size q (gather, fancy-index temporary, sum) = 4q;
   for descendant far blocks each chunk is at most q/4. So I expect peak <= 4q
   plus small index overhead everywhere, i.e. I expect Codex's claim to hold.
   Acceptance: no query above 4q + 1 MiB. A single violation refutes it.
   Not covered: native BLAS scratch, other oracles, forced dense fallbacks on
   degenerate trees beyond these two.

C. 32k capped pair at 2,900 MiB. Own cap mechanism (override of the factor's
   storage budget), own per-call recording. Two pairs, order
   production / sequential / sequential / production, untraced, nothing else
   running. Record build attempts, storage rejections, inverse size,
   corrections and GMRES columns per call, seconds per phase, peak, and
   bitwise comparison of complete arrays.
   Predictions: production first build rejected (needs 3,035 MiB), retry
   admitted; sequential admitted first time (needs 2,843 MiB); sequential
   solution bit-identical to my earlier 32k reference.
   Acceptance for a timing benefit: both sequential runs faster than both
   production runs by more than the spread within pairs.
