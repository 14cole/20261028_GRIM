# Review of Codex's leaf-query review (commit 5469680)

Reviewed: `audits/codex-2026-11-16/leaf-query-review/REVIEW_AND_HANDOFF.md`
on `codex/leaf-query-review-2026-11-16`.
Research only; no production file is changed.

`INDEPENDENT_CHECK_PLAN.md` was written before any run, after reading Codex's
report, its patch and hook source, and the production `BlockRow` class, but
before opening its check scripts or results.

## Summary

1. **Codex's correction of my statement is right.** I wrote that outside the
   690 MiB window the two builds behave identically. At 650 MiB production
   fails and the sequential build passes. Reproduced.
2. **The gather patch is safe on every path that can reach it.** 16,401 of my
   own randomised comparisons give identical values. Only one production
   caller can take the new branch, and it does not depend on the returned
   array's layout, which does change.
3. **The sequential build holds at 32,768 unknowns.** Solutions are
   bit-identical to production. Its accounted inverse storage never exceeds
   the final size (929.6 MiB), against a production high-water of 1,121.6 MiB.
4. **The leaf-query shortfall grows with size.** At 32k the production query
   allocates 23.0 MiB against a declared 2.0 MiB, at each of 128 leaves. With
   Codex's direct gather it allocates 3.2 MiB, which its `4q + 1 MiB` rule
   covers.
5. **`4q + 1 MiB` is not a general bound**, as Codex also says. I predicted
   and measured the specific gap: a stored low-rank block whose rank exceeds
   the query side. No physical case here has such a rank.

## Evidence labels

Fresh solve (FS), fresh allocation audit (FA), fresh unit test (FU),
saved-array replay (RP), source inspection (SI).

## 1. Replay of Codex's evidence (RP, FU)

- `unpack_evidence.py`: 20 array files, 55 records, all hashes verified.
- `analyze.py` on the restored arrays equals `replayed-analysis.json`.
- `check_query.py` and `check_full_query.py` exit 0 here.
- `git apply --check candidate-gather.patch` passes on Codex's tree.

## 2. Capacity at 650 MiB (FS)

Multilayer TM, 9,478 unknowns, unpacked, my instrumentation.

| Build | Outcome | Build attempts | Final inverse MiB | Corrections per call (4 condition, 1 field) | Density vs Dense |
|---|---|---:|---:|---|---:|
| production | rejected: retry needs 183.78 MiB, allowance 174.1 | 2 | — | — | — |
| Codex corrected sequential | passes all gates | 2 | 170.69 | 5, 5, 5, 5, 5 | 5.38e-10 |

Codex's table reproduces. My sentence should have read: the two builds behave
identically only where both get their first build or neither gets any; between
those, the sequential order also admits the retry inverse at lower caps.

The 690 MiB timing pair was my measurement last round and Codex has now
reproduced it (12.6% against my 11%). I did not run it a third time.

## 3. Gather patch (SI, FU)

Source: `BlockRow.values` has three callers.

| Caller | Arguments | Can reach new branch |
|---|---|---|
| `hmatrix.py:1036` | `(None, slice)` | no |
| `hmatrix.py:1388` | `(None, slice)` | no |
| `hmatrix.py:1212` (`_get_positions`) | two 1-D integer arrays | yes |

The one caller that can reach it does `result[np.ix_(...)] += row.values(...)`,
so only values, shape and dtype matter.

`claude_gather_tests.py`, written before reading Codex's tests:

- 16,401 comparisons of original against patched `values`: index dtypes
  int32, int64, uint32, intp; repeated, unsorted, negative and empty indices;
  C-order, F-order and strided `u`; complex128, complex64 and float64; list,
  boolean and slice selectors; 2-D index arrays; the low-rank path.
- **Zero mismatches** in values, shape or dtype.
- Out-of-range indices raise `IndexError` in both.
- **Layout does differ, as expected:** on the new branch the patched result is
  a C-contiguous array that owns its data; the original returns an
  F-contiguous view of an intermediate copy. Not relevant to the one caller,
  but anyone adding a caller that relies on layout should know.
- Allocation for a 149-entry query from one dense row, MiB:

| Partner columns | Original | Patched | Codex's figures |
|---:|---:|---:|---|
| 512 | 1.506 | 0.465 | 1.506 / 0.465 |
| 4,096 | 9.655 | 0.465 | 9.655 / 0.465 |
| 32,768 | 74.842 | 0.465 | 74.842 / 0.465 |

Verdict: the indexing change is correct and I see no reason against it. It is
still an unapplied patch; I have not run the production test suite with it.

## 4. Leaf-query workspace (FA, FU)

My allocation audit, as last round. The audit wrapper sits outside Codex's
pricing hook, so it reports growth against the original `2q` declaration; the
priced declaration is given alongside.

| Case | Build / query | Leaves | Declared 2q MiB | Tracked growth MiB | Codex priced 4q+1 MiB | Covered by priced |
|---|---|---:|---:|---:|---:|---|
| Multilayer 9.5k | production (last round) | 64 | 0.68 | 5.42 | — | — |
| Multilayer 9.5k | corrected sequential, direct gather | 64 | 0.68 | 1.16 | 2.36 | yes |
| Star 32k | production | 128 | 2.00 | 23.03 | — | — |
| Star 32k | corrected sequential, direct gather | 128 | 2.00 | 3.16 | 5.00 | yes |

- The production shortfall is not a fixed 5 MiB: it is 22 MiB per leaf at
  32k, because the dense partner rows are wider. It is still transient and
  sequential, so it adds at most about 22 MiB to a 3.7 GiB process.
- With direct gather the growth is about 3.2q at 32k and 1.7q on the
  multilayer, above the existing `2q` and inside `4q + 1 MiB`.
- With direct gather and pricing, the multilayer run has zero shortfalls
  above 1 MiB at any guard.

Low-rank contributions (synthetic, one block row, full leaf query):

| Query side | Stored rank | Peak including result MiB | 4q + 1 MiB | Exceeds |
|---:|---:|---:|---:|---|
| 149 | 32 | 1.16 | 2.36 | no |
| 149 | 149 | 1.69 | 2.36 | no |
| 149 | 600 | 3.75 | 2.36 | yes |
| 149 | 2,000 | 10.11 | 2.36 | yes |
| 256 | 159 | 4.24 | 5.00 | no |
| 256 | 384 | 6.00 | 5.00 | yes |

- The operands of `u[rows] @ v[:, columns]` are `rank × (rows + columns)`,
  which a multiple of q does not bound once rank exceeds the query side.
- Physical ranks here are below the leaf size: 98 against 223 (multilayer),
  159 against 256 (star 32k). The (256, 159) row above is the 32k star's
  worst case and fits.
- A sound contract needs a rank term, for example
  `4q + 16·r_max·(rows + columns)`, using the operator's recorded maximum
  rank. I have not implemented or tested that rule.

## 5. Sequential build at 32,768 unknowns (FS, FA)

Dielectric star, 16,384 panels, 180 angles, one thread, both runs traced.

| Quantity | Production | Corrected sequential + direct gather + pricing |
|---|---:|---:|
| Density and field vs production | — | bit-identical |
| Final inverse MiB | 929.62 | 929.62 |
| Accounted inverse high-water MiB | 1,121.62 | 929.62 |
| Operator MiB | 1,913.69 | 1,913.69 |
| Guard shortfalls outside leaf query | 0 | 0 |
| In-place / child solve: growth vs declared MiB | 147.5 / 769.0 | 51.2 / 769.0 |
| Process peak GiB | 3.707 | 3.672 |
| Refinement, field solve | 3 | 3 |
| Exact-row backward error | 1.1e-15 | 1.1e-15 |

- All three acceptance points in my plan are met.
- The production run is also bit-identical to my 32k Compressed run of two
  days ago.
- The clean-build storage threshold therefore drops by 192 MiB at this size
  (6.3% of operator plus high-water), in line with 5% at 9.5k.
- Process peak fell by 0.035 GiB (1%). Single traced runs; I treat that as no
  meaningful change, as predicted.
- Not done: a capped 32k run. The star harness fixes the storage budget at
  12 GiB, so the threshold is derived from the accounted high-water, as it was
  at 9.5k before I confirmed it with capped runs there. Also not done: 64k
  (about 12 GiB here, no margin under tracing), any threaded run.

## 6. Position on Codex's conclusions

- Agreed on every decision: original prototype retired, packing off, no
  tolerance change, sequential build is a storage-cap and workflow benefit and
  not a process-memory saving.
- The gather patch is the first change in this series that I would support
  for production as it stands, subject to the production test suite and a
  look at whether a rank-aware workspace declaration should accompany it.
- Unchanged open items: operator and assembly memory, Windows BLAS for the
  F-output product, real memory pressure on a 32 GB machine.

## 7. Disclosures

- Suite K reuses Codex's `corrected_builder.py`, `query_hook.py` and geometry
  generator (the objects under review); the audit, per-call recording and
  gather tests are mine. The Dense anchor is my solve from three rounds ago.
- Both 32k runs and one multilayer run are under allocation tracing: no
  timing conclusions. The two 650 MiB runs are untraced.
- The first version of my gather test script contained an invalid test case
  (a 2-D index that the original code itself rejects with a second selector
  out of range). I corrected the case and reran; the log is from the rerun.
- The gather tests ran while suite K was running.
- No failed launches. The production 650 MiB rejection is the expected result.
- Densities are not published; fields and JSON records are.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `claude_gather_tests.py`, `.json`, `.log`
- `claude_audit.py`, `claude_run_star.py`, `claude_run_geometry3.py`,
  `claude_run_suite.py`
- `claude_K.json`, `claude_K.log`
- `results/`: JSON, hook records, stdout/stderr and fields for the five runs
