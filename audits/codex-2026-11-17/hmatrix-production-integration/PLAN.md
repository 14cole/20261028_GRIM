# Production integration plan

Base production: 5fec63200d48d6dd7536221d992b3e1836a1647c; proposed publication
parent c536f7e7ab5dc12692e02c0035d3ad653299905f (same production). Reviewed
prototypes: sequential-readiness-review/corrected_builder.py and
candidate-gather-v2.patch, with later lifecycle closure accepted.

1. Add the validated dense BlockRow gather fast path, preserving empty and
   generic selector behavior. Implement the sequential inverse build only for
   HMatrixSystem; leave generic CompressedSystem and Dense paths unchanged.
   Keep double precision and all acceptance/admission rules. Charge aligned
   diagonal queries at 4q+1MiB, limited to the HMatrix fallback-size contract.
2. Preserve small-node dense fallback, sequential large-node build order,
   aliased child solves, conservative child scratch, and live correction-matrix
   accounting. Do not integrate research packing or leaf equilibration.
3. Focused actual-code tests: selector equivalence, normal/transpose/adjoint
   inverse action, zero/unequal ranks, fallback, rejection, constrained storage,
   accounting and cancellation. Verify unchanged generic backend sources.
4. Fresh production-code physical suite against baseline and Dense references:
   star and upgrading slot, 180 monostatic angles, condition estimation, exact
   rows, threads, cancellation with ledger and fallback injection. Preserve
   full fields/densities/RHS and all raw records, not only summary metrics.
5. Fresh isolated baseline/candidate runtime and peak-RAM comparisons, including
   the previously meaningful 32768-unknown star/2900MiB storage cap. Distinguish
   admission-driven policy changes from matched-policy speed or RAM claims.
6. Publish concrete production diff, reproduction scripts, lossless evidence,
   measured limitations and a Claude handoff requesting independent tests
   before cross-analysis. No merge to main or distribution certification.
