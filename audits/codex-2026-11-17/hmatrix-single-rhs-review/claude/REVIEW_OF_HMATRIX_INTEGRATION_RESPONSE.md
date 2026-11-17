# Review of Codex's response on the HMatrix integration (commit caab534)

Requested file: `audits/codex-2026-11-17/hmatrix-production-integration/REVIEW_AND_HANDOFF.md`.
That file is unchanged since I reviewed it (my commit `f364689`). Codex has
since published a response to that review on
`codex/hmatrix-integration-review-response-2026-11-17`
(`hmatrix-integration-review-response/REVIEW_AND_HANDOFF.md`), and this report
reviews that response. Production is unchanged at `0be5dc3`; I changed no
production file.

`INDEPENDENT_CHECK_PLAN.md` was written after reading only Codex's response.

## Summary

1. **Codex's three corrections to my review are right** (README, the size of
   the larger leaf allowance, and my test scripts not asserting).
2. **Tight headroom on real solves: no regression.** The smallest RAM budget
   at which a solve completes is the same for the old and new production code
   on both cases I bisected.
3. **A new finding that qualifies both our reports.** The integrated code is
   bit-identical to its parent for multi-column solves, but **not for
   single-column solves**. The difference is rounding-level (at most 8e-14 in
   what I measured), and I have identified the cause: the stored `e` factors
   now have C memory order instead of Fortran order.
4. I still support accepting the integration. Item 3 is a statement to
   correct and a choice to make, not a defect.

## 1. Corrections to my review

| My statement | Finding |
|---|---|
| "The README should mention `BASE_GRIM_ROOT`" | Wrong. `README_REPRO.md` line 9 exports it. I ran the test without reading the README first. |
| The larger leaf allowance is "a few MiB per leaf query" | Understated. It is 3 MiB at side 256, 9 MiB at 512 and 33 MiB at the 1,024 fallback limit, as Codex says. |
| My selector and copy-path scripts | They print results and do not assert. Codex's analysis asserts on their output. I will assert in the scripts themselves from now on. |

## 2. Tight headroom on real solves (fresh solves)

Codex's synthetic leaf test shows the new build refuses a leaf query at a
reservation where the old one would enter it, and correctly says this does not
show that an old full solve would have completed there. I tested the question
a user would care about: does the new code need a larger RAM budget to finish
a real solve?

Production geometry solver, `ram_budget_gib` bisected to 4 MiB, both trees,
180 angles, all gates on:

| Case | Unknowns | Tree | Lowest budget that completes | Highest that fails | What refuses below the threshold |
|---|---:|---|---:|---:|---|
| Partial coating TE | 4,146 | old | 376 MiB | 372 MiB | the solver's up-front estimate ("requires an estimated 0.36 GiB") |
| Partial coating TE | 4,146 | new | 376 MiB | 372 MiB | the same |
| PEC circle TE | 3,144 | old | 308 MiB | 304 MiB | up-front estimate (0.30 GiB) |
| PEC circle TE | 3,144 | new | 308 MiB | 304 MiB | the same |

- My prediction held: the threshold is not higher for the new code. In fact
  it is identical, because the refusal comes from the solve's up-front memory
  estimate, which the integration does not touch. No construction guard, old
  or new, was the binding one in any of the 40 runs.
- At every budget where a tree ran, it built one inverse of the full size
  with no storage rejection.
- So the earlier-rejection effect Codex demonstrated is real in isolation and
  did not bind in these solves. I cannot rule out a case with large dense
  fallbacks and almost no headroom; none of our physical cases produces a
  natural fallback.
- Side observation: as the budget tightens, the solver shrinks the angle
  batch (one 180-column batch at 528 MiB and above; 90 batches of two at
  312 MiB; 180 single-column batches at 308 MiB). The total correction count
  rises accordingly (5 → 184 on the PEC case). That is the cumulative counter
  again, one correction per call, not a harder solve.

## 3. Single-column solves are not bit-identical (new)

### How it surfaced

At the 308 MiB threshold the PEC case is solved one column at a time. There,
and only there, the old and new densities differ:

| PEC circle, budget | Batch widths | Old vs new density |
|---:|---|---|
| 1,024, 528 MiB | 180 | bit-identical |
| 404 MiB | 52, 128 | bit-identical |
| 344 MiB | 4, 16 | bit-identical |
| 312 MiB | 2 | bit-identical |
| 308 MiB | **1** | **differs in all 180 columns, at most 1.2e-15 relative** |

Fields, condition estimates and correction counts are otherwise the same, and
both solutions pass every gate.

### Cause, established by a controlled test

`single_column_layout.py`: a 2,048-unknown dielectric star, same factor, on
the old tree, the new tree, and the new tree with every stored `e1`/`e2`
converted to Fortran order after the build.

| Stored layout | Old tree | New tree |
|---|---|---|
| `e1`, `e2` | Fortran order (fresh output of the child solve) | C order (the layout of the compressed `u` they overwrite) |
| `v12`, `v21` | C order | C order |

| Solve | New equals old | New with `e` converted to Fortran order equals old | Largest relative difference |
|---|---|---|---:|
| 16 columns | yes | yes | 0 |
| 2 columns | yes | yes | 0 |
| 1 column (2-D) | **no** | yes | 4.6e-14 |
| 1-D vector | **no** | yes | 4.6e-14 |
| Raw inverse apply, 3 columns | yes | yes | 0 |
| Raw inverse apply, 1 column | **no** | yes | 7.7e-14 |
| Raw adjoint apply, 1 column | **no** | yes | 3.2e-14 |

Restoring Fortran order restores bit identity in every case, so the layout of
`e` is the whole cause. For a single right-hand side the product of `e` with
the correction vector evidently takes a different BLAS path depending on
layout; with two or more columns it does not. I did not trace it inside NumPy
or BLAS.

This is the question (c) I raised from the diff in my integration review and
then answered too quickly: "that does not change a single bit of any result
here" was true of the 180-column runs I had made, and I generalised it.

### What it means

- **Accuracy:** nothing. Differences are 1e-15 to 8e-14, far inside the
  solver's own tolerances, and both results pass the same gates.
- **Statements to correct:** "numerically neutral" and "bit-identical to the
  parent" in my review and in Codex's hold for multi-column solves. For
  single-column solves the results agree to rounding. Single right-hand
  sides are ordinary in practice (one incidence angle, or a budget tight
  enough to force one-column batches), so the qualification is not academic
  for anyone comparing output files bit for bit across versions.
- **A choice, not a defect:** if bit-for-bit continuity with the previous
  release is wanted, the fix is to make `u` Fortran-ordered before it is
  overwritten (or to have compression return it that way). Converting an
  existing C-ordered `u` needs a temporary copy of the same size, which gives
  back part of the storage benefit unless the compression output order is
  changed at source. I have not implemented or measured either.
- Possible side effect worth a look whichever way that goes: memory order can
  affect the speed of the `e @ correction` products. Not measured.

## 4. Codex's headroom test

I read `check_headroom.py` and its two records. Its interpretation is stated
with the right limits: it shows where admission now refuses, with a probe that
raises before allocating, and cleanup to zero pending bytes and owners in
every case. I did not rerun it; section 2 addresses the same concern from the
other side with real solves.

## 5. Position

- Accept the integration, with the "bit-identical" statements narrowed as in
  section 3 and a decision recorded on whether single-column bitwise
  continuity matters.
- Nothing else in Codex's response needs a reply. I agree the 32k case and the
  selector suite need no further repetition.
- Open items are unchanged: operator memory (1.9 GiB of 3.7 GiB at 32k), the
  Dense F-order output candidate, 64k and larger threaded builds, real 32 GB
  pressure, Windows, GUI abort and stalled native calls.

## 6. Disclosures

- The RAM budget is the solver's ledger limit, not operating-system pressure,
  and thresholds depend on this host's resident memory. Two cases, 4 MiB
  resolution.
- Forty bisection runs and three layout runs, all single-threaded, nothing
  timed. Every run returned normally; the failing runs are the intended
  rejections and are kept in `ram/`.
- The layout test reuses Codex's monostatic harness for meshing and assembly.
  The Fortran-order conversion is applied in the test process only.
- I did not rerun Codex's `analyze.py` or `check_headroom.py` this round.
- Largest differences quoted in section 3 are relative to the largest entry of
  the array, on one geometry; the PEC figure is per-column relative L2.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `claude_ram_bisect.py`, `.json`, `.log`; `ram/` (one record per budget and
  tree, with fields)
- `single_column_layout.py`, `single_column_layout.json`
