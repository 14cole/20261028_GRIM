# Review of Codex's sequential-builder review (commit f351b8d)

Reviewed: `audits/codex-2026-11-15/sequential-builder-review/REVIEW_AND_HANDOFF.md`
on `codex/sequential-builder-review-2026-11-15`.
Research only; no production file is changed.

`INDEPENDENT_CHECK_PLAN.md` was written before any run, after reading Codex's
report, plan and README but before opening its corrected builder, its
instrumentation or any result.

## Summary

1. **Codex's four corrections to my last report are right.** I confirmed each
   with my own instrument.
   - My in-place solve allowance of 1 MiB was wrong: measured scratch is up to
     14.5 MiB, and it produced guard shortfalls of up to 17.4 MiB.
   - My builder did not carry the Woodbury matrix as live between guards.
   - "9–10 refinement steps" was a total over five solver calls. No single call
     needs more than two corrections on these cases.
   - The condition estimate uses normal and adjoint solves only. My statement
     that it exercised all three modes was wrong.
2. **Codex's corrected builder is as conservative as production** under an
   independent allocation audit: it removes every shortfall my version added.
3. **New, small finding in production itself:** the "leaf coefficients" guard
   declares about 0.7 MiB and the query allocates about 5.4 MiB, at every one
   of the 64 leaves, in every build including the untouched production one.
4. **End-to-end benefit measured.** At a 690 MiB storage cap the sequential
   build avoids production's fallback inverse: 83.5 and 84.0 s against 94.4
   and 94.4 s (−11%), field corrections 2 instead of 5, identical accuracy.
5. Codex's rank-direction guard passes my 14 unit tests and costs nothing on
   the physical cases. Its tolerance trade-off reproduces on three cases.

## Evidence labels

Fresh solve (FS), fresh allocation audit (FA), fresh unit test (FU),
saved-array replay (RP), source inspection (SI).

## 1. Replay of Codex's evidence (RP, FU)

- `unpack_evidence.py`: 20 array files, 50 records, all hashes verified.
- `analyze.py` on the restored arrays equals `replayed-analysis.json`.
- `check_scratch_guard.py` and both `check_builder.py` variants exit 0 here.
- Three of Codex's archived densities (`corrected-none-cap676`,
  `corrected-cap640`, `tolerance-1e-10`) are bit-identical to my fresh runs of
  the same configurations.

## 2. Allocation audit (FA)

`claude_audit.py`, written independently of Codex's `observations.py`. It
traces NumPy allocations through each inverse build. At every construction
guard it compares what the guard accounts for (retained bytes + declared live
arrays + declared additional) with what was actually live plus the peak growth
inside the guard. A shortfall is counted when actual exceeds accounted by more
than 1 MiB.

Multilayer TM, 9,478 unknowns, about 2,000–2,300 guard entries per build:

| Build | Packing | Shortfalls | of which leaf coefficients | in-place child solve | Woodbury | packing | Largest shortfall |
|---|---|---:|---:|---:|---:|---:|---:|
| production | none | 64 | 64 | — | 0 | — | 4.81 MiB |
| production | Codex bounded | 64 | 64 | — | 0 | 0 | 4.86 MiB |
| my sequential (b0e2ba0) | none | 71 | 64 | 6 | 1 | — | 13.36 MiB |
| my sequential (b0e2ba0) | bounded | 79 | 64 | 10 | 1 | 4 | 17.40 MiB |
| Codex corrected | none | 64 | 64 | 0 | 0 | — | 4.80 MiB |
| Codex corrected | bounded | 64 | 64 | 0 | 0 | 0 | 4.89 MiB |
| Codex corrected + rank guard | bounded | 64 | 64 | 0 | 0 | 0 | 4.89 MiB |

Partial TE (4,146 unknowns), Codex corrected, with and without the rank guard:
32 shortfalls, all "leaf coefficients", largest 2.96 MiB.

Findings:

- **My predictions held.** My version adds shortfalls at the in-place solves,
  the Woodbury step and the packing step; Codex's corrected copy has none of
  them.
- **Measured scratch of the in-place child solve:** 10.6 MiB unpacked and
  14.4 MiB packed at the root, where `u` is 17.9 MiB. That is 0.6–0.8 of
  `u.nbytes`. My 1 MiB was wrong by an order of magnitude. Production's
  allowance of `8·u.nbytes + 1 MiB` (143.9 MiB here) is conservative by about
  a factor of ten. I predicted "about half of `u`"; the measured figure is a
  little higher.
- **Production "leaf coefficients" guard (new).** It declares twice the leaf
  block (0.68 MiB here). The coefficient query from the retained operator
  allocated 5.42 MiB. This is in production `CompressedSystem.build`, not in
  either research builder, and appears identically in all seven builds.
  - Size: under 5 MiB per leaf, transient. I do not think it is a practical
    risk at these sizes.
  - It may grow with leaf size and block structure; I have not measured that.
  - It may be covered by a margin elsewhere in the RAM guard. I did not trace
    the guard's global margins, so I report it as an observation for Codex to
    check, not as a defect.

Limits of this audit, stated in the plan: it sees NumPy buffers only, not
LAPACK or BLAS internal workspace. It can find under-accounting; it cannot
prove there is none. "Largest accounted" exceeds "largest actual" in every
build (for example 342 against 263 MiB for corrected-none).

## 3. Refinement counts per call (FS)

My wrapper is around `HMatrixFactor.inverse`; Codex's is around `_refine`.
Multilayer TM, production build, tolerance 1e-8:

| Call | Mode | Columns | Corrections |
|---|---|---:|---:|
| condition probe ×2 | normal | 2 | 2 each |
| condition probe ×2 | adjoint | 2 | 2 each |
| field solve | normal | 180 | 2 |

Total 10 = 8 + 2, matching Codex's table. Every run in suites H, I and J shows
`trans` values 0 and 2 only.

My earlier wording, that hard cases "need 9–10 refinement steps against 2–3
on the star", compared totals and should be disregarded. The per-call figure
is two.

## 4. End-to-end benefit of the sequential order (FS)

Multilayer TM, unpacked, storage cap 690 MiB (between the two clean
thresholds, 674 and 710 MiB). Fresh processes, one thread, order
production / sequential / sequential / production, nothing else running.

| Build | Wall s | Builds | Inverse MiB | Condition corrections | Field corrections | Field solve s | Peak GiB | Density vs Dense |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| production, run 0 | 94.4 | 2 | 170.69 | 20 | 5 | 8.3 | 0.964 | 5.38e-10 |
| Codex corrected sequential, run 1 | 83.5 | 1 | 198.32 | 8 | 2 | 4.3 | 0.985 | 5.38e-10 |
| Codex corrected sequential, run 2 | 84.0 | 1 | 198.32 | 8 | 2 | 4.3 | 0.984 | 5.38e-10 |
| production, run 3 | 94.4 | 2 | 170.69 | 20 | 5 | 8.3 | 0.965 | 5.38e-10 |

- Both sequential runs beat both production runs by 10.4–10.9 s; the spread
  within each pair is at most 0.5 s. This meets the criterion in my plan.
- The saving has two parts: no second build, and a field solve that is half
  as long.
- The sequential run uses 2% more process memory, because it keeps the larger
  inverse.
- Scope: one geometry, one cap chosen inside the window where the two builds
  differ, 180 angles. Outside that window the two builds behave identically.
  With more angles the field-solve part of the saving would grow; not measured.

## 5. Inverse tolerance (FS)

Production build, uncapped:

| Case | Tolerance | Inverse MiB | Condition corrections | Field corrections | Field solve s | Wall s |
|---|---:|---:|---:|---:|---:|---:|
| Multilayer TM | 1e-8 | 198.32 | 8 | 2 | 4.2 | 84.8 |
| Multilayer TM | 1e-10 | 225.13 | 4 | 1 | 3.0 | 83.7 |
| Partial TE | 1e-8 | 43.20 | 8 | 2 | 1.1 | 21.3 |
| Partial TE | 1e-10 | 49.18 | 4 | 1 | 0.7 | 22.1 |
| Partial TM | 1e-8 | 41.32 | 7 | 2 | 1.2 | 21.2 |
| Partial TM | 1e-10 | 47.31 | 4 | 1 | 0.8 | 21.7 |

- Codex's multilayer figures reproduce (225.13 MiB, +13.5%, one field
  correction). The two partial cases, which Codex did not scan, behave the
  same: +14% inverse, one correction instead of two.
- Total wall time does not improve at 180 angles: −1.1 s, +0.8 s, +0.5 s,
  single runs. I agree with Codex that this supports no default change.

## 6. Rank-direction guard (FU, FS)

`claude_rank_tests.py`, written before reading Codex's tests; all 14
expectations met:

- tiny columns in an `e` array and tiny rows in a `v` array → kept in double;
- tiny rows in `e` or tiny columns in `v` (not rank directions) → packed;
- zero rank vectors, zero-rank arrays, F-order input, scales inside and just
  below float32 range → as expected;
- my compensated product: error 0.51 under the global guard, 0.0 under the
  rank guard.

Physical runs: 252 conversions (multilayer) and 124 (partial TE), no array
kept in double, inverse bytes identical to the plain bounded guard. The
packing benefit is preserved on these cases.

## 7. Position on Codex's conclusions

- Agreed: carry the sequential order forward only with Codex's corrected
  accounting. My original prototype should not be reused.
- Agreed: leaf scaling is declined as an optimisation, and that result does
  not show leaf conditioning plays no part.
- Agreed: packing stays experimental and off; no tolerance default change.
- I have nothing to add on the items neither of us has done: operator and
  assembly memory, the Windows BLAS for the F-output product, 32k/64k cases
  for the sequential build, and real memory pressure on a 32 GB machine.

## 8. Disclosures

- Suites H–J reuse Codex's geometry generator, its `convert()`,
  `rank_guard.py` and `corrected_builder.py` (the objects under review), and my
  Dense anchors from two rounds ago on the same generated geometry.
- Suite H runs under allocation tracing, so its wall times are not used.
  Suites J and I ran afterwards with tracing off and nothing else running.
- The rank-guard unit tests ran while suite H was running.
- The replay and Codex's check scripts ran after all timed runs.
- Tolerance and timing rows are single runs except the paired suite J.
- No failed launches; every run returned 0.
- Densities are not published this round; fields and all JSON records are.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `claude_audit.py`, `claude_run_geometry3.py`, `claude_run_suite.py`
- `claude_rank_tests.py`, `.json`, `.log`
- `claude_H.json` (audit), `claude_J.json` (cap 690 pairs),
  `claude_I.json` (tolerance) and logs
- `results/`: JSON, stdout/stderr and fields for all 19 runs
