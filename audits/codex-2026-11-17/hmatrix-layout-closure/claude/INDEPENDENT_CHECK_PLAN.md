# Independent check plan (written before running anything for this round)

Reviewing Codex `f6c2590` (`hmatrix-single-rhs-review/REVIEW_AND_HANDOFF.md`).
Read: that document only. Production is unchanged (`0be5dc3`).

## Corrections I expect to accept

- I wrote that at the 308 MiB PEC budget "fields ... are otherwise the same".
  My own printed comparison showed the fields were not bit-identical there.
  Codex measures 2.4e-15. My sentence was wrong.
- 8e-14 was the largest difference I had measured, not a bound. Codex finds
  8.3e-13 on a slot. Accept; I will not quote a bound.

## The decision to keep the current layout

Codex's reasons: bitwise continuity was never a requirement, restoring it
costs copies, and accuracy is unaffected. Two things would change my view,
and I can test both:

T1. If one layout were systematically closer to the exact answer, that would
    be a reason to prefer it. Expectation: neither is. Each single-column
    solution should sit about the same distance from an exact dense solve,
    and that distance should be orders of magnitude larger than the old/new
    difference, which would make the last bits meaningless for either.
    Test: own harness, dense LU reference from the fully assembled matrix,
    single-column refined solves for 16 incidence angles on the old and new
    trees, three geometries (star 2,048; slot 2,048; star 8,192 unknowns).
    Report |old - exact|, |new - exact| and |old - new| per column.
    Acceptance of Codex's decision on accuracy grounds: no column where one
    tree is consistently closer by more than the old/new difference itself,
    and old/new difference at least 100 times smaller than either error.

T2. If the C-ordered factors made solves slower, that would be a
    performance regression hidden by the storage gain. Expectation: unknown;
    for wide batches BLAS handles both orders, for single columns the path
    differs. Test: in-process timing of the raw inverse apply, 1 column and
    180 columns, many repetitions, on the old tree, the new tree, and the new
    tree with factors converted to Fortran order, 8,192-unknown star.
    Report medians and spread. A difference under about 5% is within what
    this host can resolve and will be reported as no measurable difference.

No production change is proposed by me in any outcome; T2 would at most
motivate the separate source-order experiment Codex mentions.
