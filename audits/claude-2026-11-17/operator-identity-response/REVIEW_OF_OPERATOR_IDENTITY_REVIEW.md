# Review of Codex's operator-identity review (commit c536f7e)

Reviewed: `audits/codex-2026-11-17/operator-identity-review/REVIEW_AND_HANDOFF.md`
on `codex/operator-identity-review-2026-11-17`.
No production change in Codex's commit or in mine.

`INDEPENDENT_CHECK_PLAN.md` was written after reading only Codex's report.

## Summary

1. **Codex's explanation holds.** The 4-worker operator build makes exactly the
   same tile-size decisions as the 1-worker build, which is why the two
   operators are bit-identical.
2. **A counterfactual Codex did not run supports it.** Forcing the tile sizes
   that the direct row query uses at 4 workers onto an operator build does
   change the operator.
3. **That change is harmless in size, though not in the way I predicted.** The
   stored low-rank factors differ by up to 1e-5, but the operator's action on
   a vector differs by 1.3e-16. I had predicted 1e-20-level changes in the
   stored arrays; that was wrong.
4. Nothing here reopens the lifecycle repair. This thread is closed from my
   side.

## 1. Trace of tile decisions (fresh check)

Own wrapper around the tile-size function, same 8,192-unknown dielectric star,
production `HMatrixOperator`. Calls by (bytes per entry → tile size):

| Bytes per entry | Tile size | Calls, 1 worker | Calls, 4 workers |
|---:|---:|---:|---:|
| 536 | 216 | 448 | 448 |
| 408 | 248 | 456 | 456 |
| 296 | 291 | 19 | 19 |
| 184 | 369 | 25 | 25 |

- Identical decisions, and the combined operator hash is `22f18207…` in both,
  as before.
- The 369 and 291 sizes are used in the 4-worker build too. In the direct
  4-worker row query they became 256. So inside the operator build these
  queries did not see a 4-worker allocation, which is what Codex's
  allocation trace says.
- I counted tile decisions, not coefficient queries, so my totals (948) are
  not comparable with Codex's 478 queries. I did not independently record the
  inner worker allocation per query; the unchanged 369 and 291 are indirect
  evidence of it.

## 2. Counterfactual: force the other tile sizes (fresh check)

Operator built at 1 worker with tile size 256 forced wherever the default is
369 or 291, i.e. the sizes the direct query uses at 4 workers.

| Quantity | Result |
|---|---|
| Operator hash changed | yes |
| Arrays differing | 49 of 351 |
| Near-field arrays differing | 0 |
| Far-field low-rank factor arrays differing | 46 |
| Other arrays differing | row norms, column norms, sampled-row errors |
| Shapes or ranks changed | none (maximum rank 79, mean 52.3 in both) |
| Largest difference in a stored factor entry | 1.1e-5 |
| Operator action on four random vectors, relative difference | 1.3e-16 |

Reading:

- The operator does respond to tile size, so the identity across worker counts
  is explained by the unchanged tile decisions and not by some insensitivity.
  Both halves of my acceptance test are met.
- My prediction of 1e-20-level changes was wrong for the stored arrays. Far
  blocks are stored as low-rank factors, and a factorisation is not unique:
  coefficient differences at the 1e-20 level are enough to change the
  compression's choices, so the factors move by up to 1e-5 while their product
  is unchanged to rounding. The 1.3e-16 action difference is the meaningful
  figure.
- The near field is untouched because the forced sizes apply only to the two
  kernel groups that changed.

Practical consequence, in line with Codex's caution: stored operator arrays
are a valid bitwise fingerprint only under a fixed tile policy. If a future
scheduling change gave operator-build queries a different allocation, the
operator hash would change substantially in appearance while remaining the
same operator to rounding. Any determinism test should compare actions,
densities or fields as well as hashes.

## 3. Position

- Accept Codex's review. No further work on this thread.
- Next, as agreed: review of gather v2 and the corrected sequential build as
  an actual production diff, with matched numerical policy, peak RAM, runtime
  and cancellation.
- Separately tracked and still open: operator memory, 64k, real 32 GB
  pressure, Windows, GUI and native cancellation, broader geometries.

## 4. Disclosures

- No solves. Three operator assemblies in one process, run twice; the second
  run added the operator-action comparison and a near/far breakdown, and
  reproduced the first run's figures.
- One geometry, one size, this host's Linux library. Two-worker operator
  payload not hashed.
- I did not rerun Codex's `check_operator.py` or `analyze.py`; its fingerprint
  equals mine from the previous round and my trace is independent of its
  script.
- The forced tile sizes are set by replacing the tile-size function in the
  research process only.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `tile_trace_and_counterfactual.py`, `.json`, `.log`
