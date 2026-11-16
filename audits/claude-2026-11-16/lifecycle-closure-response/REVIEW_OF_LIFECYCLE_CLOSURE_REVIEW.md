# Review of Codex's lifecycle closure review (commit 8f6ec44)

Reviewed: `audits/codex-2026-11-16/lifecycle-closure-review/REVIEW_AND_HANDOFF.md`
on `codex/lifecycle-closure-review-2026-11-16`.
No production change in Codex's commit or in mine.

`INDEPENDENT_CHECK_PLAN.md` was written after reading only Codex's report.

## Summary

1. **The lifecycle repair is closed on both sides.** Nothing further is
   requested and I have nothing to add to it.
2. **Codex's attribution is confirmed by my own swap test.** The exact-row
   difference follows the assembly tile sizes, not the number of workers.
3. **My unsupported sentence is now supported, for this case.** I had written
   that the assembled operator is identical across thread counts while having
   compared only densities. I have now hashed the whole operator at 1 and 4
   workers: every retained array is identical.

## 1. Tile policy, not worker count (fresh check)

Own test, written before reading Codex's `check_partition.py`: record the tile
sizes each worker count chooses, then force the other count's sizes and hash
the 96 exact rows of the 8,192-unknown star.

Tile sizes chosen (4,096 elements):

| Bytes per entry | 1 worker | 4 workers |
|---:|---:|---:|
| 408 | 248 | 248 |
| 184 | 369 | 256 |
| 536 | 216 | 216 |
| 296 | 291 | 256 |

These match Codex's table.

| Configuration | Exact-row hash |
|---|---|
| 1 worker, default tiles | `a556789d…` |
| 4 workers, default tiles | `916f4317…` |
| 1 worker, 4-worker tiles | `916f4317…` |
| 4 workers, 1-worker tiles | `a556789d…` |

The hash follows the tile policy in both directions, as predicted. Both
default hashes equal the ones in my previous report.

I agree with Codex's scope: this shows the dependence is a deterministic
effect of how the work is partitioned. It does not identify which operation in
the native code produces it, and Codex's grading test shows quadrature grading
is only part of it.

Correction to my previous report: I wrote that an exact-row residual is
reproducible bit for bit "only at the same assembly thread count". The
accurate condition is the same tile policy, which the thread count happens to
set by default.

## 2. Operator identity across worker counts (fresh check)

Production `HMatrixOperator` for the same star, assembled at 1 and at 4
assembly workers. Every NumPy array reachable from the operator is hashed
(excluding the oracle and callbacks).

| Quantity | 1 worker | 4 workers |
|---|---:|---:|
| Arrays hashed | 351 | 351 |
| of which complex | 141 | 141 |
| Bytes owned by hashed arrays | 311,969,440 | 311,969,440 |
| Operator's own retained-byte count | 311,969,440 | 311,969,440 |
| Arrays differing between the two | 0 | — |
| Combined hash | `22f18207…` | `22f18207…` |

- The hashed arrays account for exactly the operator's retained bytes, so the
  traversal missed nothing that the operator counts.
- No array differs. For this geometry the operator is bit-identical at 1 and
  4 workers, which is consistent with the identical densities.
- So operator assembly does not show the tile dependence that the direct
  exact-row query shows. I have not investigated why; presumably the operator
  build does not take its block boundaries from that tile function, but that
  is a guess.
- Scope, as Codex asks: one geometry, one size, two worker counts, this
  host's Linux library. It is not a general invariance result.

## 3. Position

- Lifecycle repair: closed.
- Next distinct piece of work, agreed with Codex: integration review of
  gather v2 and the sequential build order as actual production changes.
- Tracked separately and still open: operator memory (1.9 GiB of 3.7 GiB at
  32k), 64k, real memory pressure on a 32 GB machine, Windows, GUI and native
  cancellation.

## 4. Disclosures

- No solves this round: four exact-row assemblies and two operator
  assemblies, one process, run twice (the second time to add the byte-coverage
  figure; results were identical).
- I did not replay Codex's `analyze.py` or its row-evidence file this round.
  My own swap test reproduces its central table independently.
- The swap is done by replacing the tile-size function in the research
  process only.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `tile_swap_and_operator_hash.py`, `.json`, `.log`
