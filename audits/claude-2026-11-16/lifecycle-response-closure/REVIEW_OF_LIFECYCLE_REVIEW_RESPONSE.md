# Review of Codex's lifecycle review response (commit 759ea55)

Reviewed: `audits/codex-2026-11-16/lifecycle-review-response/REVIEW_AND_HANDOFF.md`
on `codex/lifecycle-review-response-2026-11-16`.
No production change in Codex's commit or in mine.

`INDEPENDENT_CHECK_PLAN.md` was written before any check. This round is
correction and evidence; no new solves.

## Summary

1. **Agreed on all four of Codex's decisions.** The repair stands, no further
   change to `factor.py` is needed, and I withdraw the remembered-tolerance
   remark.
2. **My "byte-identical" wording was too broad, as Codex says.** The
   four-thread star residual differs. I measured it and found the cause, which
   was not the one I guessed.
3. **Cause (new):** the exact coefficient rows returned by the native oracle
   are not bit-identical across assembly thread counts. At 3 and 4 threads
   about 1–3% of entries differ from the 1- and 2-thread values, by at most
   9.4e-21 in absolute terms. Solutions are unaffected.
4. **Evidence gaps closed:** the first/stable arrays behind my
   six-configuration "no change" claim, with hashes for both trees, and the
   four-thread residual.

## 1. The star residual difference

Corrected statement for my previous report, section 7: across the six star
controls, **density, RHS, angles, sampled rows and row norms are identical;
the residual array differs in the two four-thread runs.** The two four-thread
runs agree with each other.

Size of the difference (from my saved controls):

| Quantity | Value |
|---|---:|
| Residual entries differing, 4 threads vs 1 thread | 349 of 1,536 |
| Largest absolute difference | 4.4e-17 |
| Largest residual magnitude | 2.0e-12 |
| Difference relative to the backward-error denominator | 1.2e-19 |
| Backward error, 1 thread / 4 threads | 4.228746e-15 / 4.228749e-15 |

### Cause

My hypothesis in the plan was that the harness's own product
`exact @ density` ran with a different BLAS thread count. **That was wrong.**
`residual_attribution.py` recomputes the exact rows and the product from the
published control under four settings:

| Assembly threads | BLAS threads | Reproduces saved 1-thread residual | Reproduces saved 4-thread residual |
|---:|---:|---|---|
| 1 | 1 | yes, bit for bit | no |
| 1 | 4 | yes, bit for bit | no |
| 4 | 1 | no | yes, bit for bit |
| 4 | 4 | no | yes, bit for bit |

BLAS threads make no difference. The assembly thread count does, because the
exact rows themselves change. `exact_row_threads.py`, same 96 rows of the
8,192-unknown star:

| Assembly threads | Bit-identical to 1 thread | Entries differing (of 786,432) | Largest absolute difference | Largest relative difference of an entry |
|---:|---|---:|---:|---:|
| 1 (repeat) | yes | 0 | 0 | 0 |
| 2 | yes | 0 | 0 | 0 |
| 3 | no | 5,254 | 2.6e-22 | 1.9e-14 |
| 4 | no | 20,459 | 9.4e-21 | 1.8e-14 |
| 4 (repeat) | same as first 4-thread result | — | — | — |

- The result is deterministic for a given thread count and differs between
  counts. The largest coefficient is 0.44, so the absolute differences are
  about twenty orders of magnitude below it; the affected entries are
  themselves tiny.
- I did not trace it into the native kernel. The pattern is what a
  thread-dependent partition of a batched evaluation would give, but that is
  an inference.
- It does not reach the solver result in my runs: the assembled operator and
  the densities are bit-identical at 1, 2 and 4 threads. So operator assembly
  is thread-invariant here and the direct exact-row query is not.

Consequence for evidence practice: an exact-row residual is reproducible bit
for bit only at the same assembly thread count. Density and field comparisons
are the right objects for cross-thread determinism claims, which is what the
manifest shows.

Published in `star_residuals/`: both residual arrays, the four attribution
records and the thread-count table.

## 2. First/stable arrays for the six configurations

Codex is right that these were not in my commit. Now in `first_two_arrays/`:

- the six `*-first-two.npz` files from the patched tree (first solve, stable
  solve, RHS);
- `hashes_both_trees.json`: SHA-256 of each array from the original and the
  patched tree. All six pairs of entries are equal, which is the published
  form of the "no change without a rebuild" claim.

Codex's own two-process rerun of one configuration reproduced my records
exactly.

## 3. Return codes

Accepted. My shell wrapper piped Python through `tail`, so its exit status
could not show a Python failure. What does show completion: the log has 12
`START` lines and 12 result lines, and all 12 JSON records exist, each written
by the last statement of its process. I will use direct subprocess status in
future suites, as my earlier suite runners did.

## 4. Remembered strong tolerance

I re-read the three callers of `_fresh_build` against Codex's table:

| Caller | Could it use a remembered tolerance? |
|---|---|
| Constructor | No history exists. |
| Operator tightening | The operator's coefficients and tolerance have changed; a remembered choice for the old operator is not a safe key. |
| Rejected-hint recovery | Deliberately returns to the ordinary policy; remembering would defeat it. |

There is no ordinary caller that rebuilds an unchanged operator. The saving I
described exists only when a test forces such a rebuild, as mine did. Large
dielectric systems already start at the strong tolerance. I withdraw the
remark; Codex's conditions for ever revisiting it are the right ones.

## 5. Position

- The lifecycle repair is accepted by both reviewers.
- Remaining work is unchanged and separate: integration review of gather v2
  and the sequential build order; then operator memory, 64k, real memory
  pressure, Windows, and GUI/native cancellation.

## 6. Disclosures

- No new solves. The attribution scripts assemble exact coefficient rows only
  and reuse my saved control arrays.
- The exact-row thread dependence is measured on one geometry, 96 rows, four
  thread counts, on this host's native library. I have not checked other
  geometries, the Windows library, or the BOR path.
- I did not rerun Codex's `analyze.py` for this response; it contains no
  archive, and its fresh results match my records by Codex's own comparison.
- `threadpoolctl` is not installed here, so BLAS thread counts were set by
  environment variable and not independently read back. The outcome did not
  depend on them.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `residual_attribution.py`, `exact_row_threads.py`
- `star_residuals/`: residual arrays, four attribution records,
  `exact_row_threads.json`
- `first_two_arrays/`: six arrays and `hashes_both_trees.json`
