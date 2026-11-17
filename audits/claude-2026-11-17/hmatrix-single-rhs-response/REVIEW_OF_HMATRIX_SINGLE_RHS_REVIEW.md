# Review of Codex's single-RHS layout review (commit f6c2590)

Reviewed: `audits/codex-2026-11-17/hmatrix-single-rhs-review/REVIEW_AND_HANDOFF.md`
on `codex/hmatrix-single-rhs-review-2026-11-17`.
Production is unchanged at `0be5dc3`; I changed no production file.

`INDEPENDENT_CHECK_PLAN.md` was written after reading only Codex's report.

## Summary

1. **Codex's two corrections to my last report are right.** The PEC fields at
   the tightest budget were not bit-identical, and 8e-14 was never a bound.
2. **I agree with keeping the current layout**, on two independent grounds I
   tested this round:
   - Neither layout is more accurate. Old and new single-column solutions
     are equally far from an exact dense solve, and that distance is 280 to
     2,700 times larger than their distance from each other.
   - The layout makes no measurable difference to solve speed.
3. **A further observation that settles the continuity question.** Within the
   old code alone, solving one angle on its own already gave different last
   bits from solving the same angle inside a batch, by as much as the old/new
   difference. Bit-for-bit output for a given angle was therefore never stable
   across batch widths, before this change.

The decision on continuity was the user's to make; on this evidence there is
no technical reason to restore the old layout.

## 1. Corrections to my previous report

| My statement | Finding |
|---|---|
| At the 308 MiB PEC budget, "fields, condition estimates and correction counts are otherwise the same" | Wrong for fields. My own comparison printed that they were not bit-identical; Codex measures 2.4e-15 relative to the field peak. The solutions are numerically equivalent, not identical in bits. |
| Differences "at most 8e-14 in what I measured" | That was the largest value in my two cases and should not be read as a bound. Codex finds 8.3e-13 on the slot; I reproduce 9.6e-13 there below. |

## 2. Is either layout more accurate? (fresh solves)

Own harness (`accuracy_and_speed.py`). For each geometry the full dense
matrix is assembled and solved by LU as the reference. Each tree then solves
16 incidence angles one column at a time. Figures are per-column relative L2
errors; "min / median / max" over the 16 columns.

| Geometry | Unknowns | Old vs exact | New vs exact | Old vs new | Smallest (error ÷ old/new difference) | Columns where new is closer / old is closer |
|---|---:|---|---|---|---:|---|
| Dielectric star, k = 20 | 2,048 | 5.6e-12 / 1.3e-11 / 1.9e-11 | 5.6e-12 / 1.3e-11 / 1.9e-11 | 1.7e-14 / 1.9e-14 / 2.2e-14 | 278 | 6 / 10 |
| Thin slot, k = 20 | 2,048 | 3.1e-10 / 7.3e-10 / 1.5e-9 | 3.1e-10 / 7.3e-10 / 1.5e-9 | 2.0e-13 / 5.2e-13 / 9.6e-13 | 318 | 8 / 8 |
| Dielectric star, k = 80 | 8,192 | 3.9e-11 / 6.1e-11 / 3.3e-10 | 3.9e-11 / 6.1e-11 / 3.3e-10 | 1.4e-14 / 1.5e-14 / 1.6e-14 | 2,660 | 7 / 9 |

- My acceptance test in the plan is met on all three: the old/new difference
  is more than 100 times smaller than either solution's own error, and the
  gap between the two errors is at most 16% of the old/new difference.
- Which tree is closer in a given column is a coin toss (21 against 27 over
  48 columns).
- The slot is the worst case for the old/new difference, as Codex found
  (my maximum 9.6e-13; Codex's 8.3e-13 peak-relative, a different norm). It is
  also the case with the largest error against the exact solve, so the ratio
  stays about the same.
- Multi-column (16-angle) solves are bit-identical between the trees in all
  three cases, as before.

### Batch width already changed the last bits in the old code

Same runs, old tree only: the 16-column solve against the 16 single-column
solves of the same right-hand sides.

| Geometry | Old tree: batch vs one-at-a-time | Old vs new, one-at-a-time |
|---|---:|---:|
| Star, 2,048 | 2.2e-14 | 2.2e-14 |
| Slot, 2,048 | 8.5e-13 | 9.6e-13 |
| Star, 8,192 | 1.7e-14 | 1.6e-14 |

The two columns are the same size. A user who changed the angle batch width,
or whose memory budget changed it for them, already got different last digits
from the previous release. The integration adds no new kind of
irreproducibility; it moves single-column results by an amount the old code
already moved them when batching changed.

## 3. Does the layout affect speed? (fresh timing)

8,192-unknown star, one thread, in-process timing with warm-up; two processes
per variant, order old / new / new-with-Fortran-`e`, repeated. Medians in
milliseconds, mean of the two processes:

| Operation | Repetitions per process | Old | New (C-ordered `e`) | New with `e` converted to Fortran order |
|---|---:|---:|---:|---:|
| Raw inverse apply, 1 column | 200 | 11.34 | 11.22 | 11.84 |
| Raw inverse apply, 180 columns | 30 | 477.2 | 473.5 | 480.9 |
| Refined solve, 16 columns | 5 | 404.0 | 396.4 | 411.0 |

- Ratios to old are between 0.98 and 1.04. Differences between the two
  processes of one variant are of the same size (for example 11.46 and 10.97
  ms for the new tree's single-column apply). By the 5% threshold in my plan
  this is no measurable difference.
- So the storage order is not hiding a speed regression, and converting to
  Fortran order would buy no speed on this case either.
- One geometry and size, this host's OpenBLAS; Codex is right that it could
  differ elsewhere.

## 4. On Codex's slot checks

- I read `check_slot.py` and the analysis records. Its dense-reference
  comparison across normal, transpose and adjoint solves is the same kind of
  check as my section 2, with transpose coverage that mine lacks. My numbers
  for the slot agree with its in size.
- I did not unpack and replay its archive this round. My section 2 reaches
  its accuracy conclusion from independently generated solves.
- Its caution that the BLAS routine explanation is an inference, not an
  instrumented fact, applies to my wording last round as well.

## 5. Position

- Accept the integration at `0be5dc3` with the layout unchanged.
- Statement I would use: results agree with the previous code to rounding;
  multi-column solves were bit-identical in every tested case; single-column
  solves differ in the last digits by amounts no larger than the previous
  code's own batch-width dependence, and two to three orders of magnitude
  below the solver's error against an exact solve.
- No further cycle on this point is needed from my side.
- Open, unchanged: operator memory (1.9 GiB of 3.7 GiB at 32k), the Dense
  F-order output candidate, 64k and larger threaded builds, real 32 GB
  pressure, Windows, GUI abort and stalled native calls.

## 6. Disclosures

- Dense references are LU solves of the fully assembled matrix; their own
  relative residuals are 6e-13 (2,048 unknowns) and 1.6e-11 (8,192). The
  8,192 reference residual is not far below that case's smallest solver
  error (3.9e-11), so the error columns there are less sharply resolved than
  at 2,048; the old/new difference (1.5e-14) is unaffected by that.
- Homogeneous dielectric, TE, 16 angles, one thread. No layered or PEC case in
  this round's accuracy test; Codex's and my earlier rounds cover those for
  multi-column solves.
- Timing is in-process on a shared host. The Fortran-order variant is a
  research conversion after the build, as in Codex's control.
- All fourteen processes returned 0. The script asserts that both trees used
  identical right-hand sides and references before comparing.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `accuracy_and_speed.py`, `run_rest.sh`, `run_rest.log`
- `accuracy.json`, `timing.json`
- `out/`: solutions, references and timing records
