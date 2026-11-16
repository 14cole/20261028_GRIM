# Independent review and inverse-upgrade lifecycle repair

Reviewed ecc046c report, attribution/cancellation scripts and production
callers before this plan; no new physical tests yet.

Hypothesis: `_upgrade_attempted` is bounded per factor object, although an
ordinary `_fresh_build` installs a new weaker inverse. It should be rearmed
after a successful ordinary fresh build, not after each `_build` or solve.
The rejected-hint fallback explicitly suppresses another upgrade and must
continue to do so. Failed/cancelled fresh construction must not rearm a
working old generation accidentally.

1. Rerun Claude's attribution script unchanged on the original checkout.
2. Repair the lifecycle in an isolated production checkout. Reset only on
   successful fresh-build completion; pass an explicit private suppression
   argument on rejected-hint fallback. Do not change tolerances/admission.
3. Focused tests for once-per-build attempts, denied upgrades, failures and
   cancellation, hinted early success, and explicit hint-fallback suppression.
4. Fresh slot comparisons on original and fixed code: 16-angle reproduction,
   180 angles with condition estimation, in-object cancelled rebuild/recovery
   with a memory ledger, an injected rejected-hint solve, and a controlled
   sample-row rejection invoking the real operator-tightening rebuild path.
   Preserve complete fields/densities/RHS and exact-row checks; do not assume
   bit equality between different inverse policies/operators.
5. Recompute Claude's cancellation counts from pinned records. Distinguish
   their reported 48 cases from our fresh tests; those control NPZ files and
   cross-thread density hashes are not included in this commit.
6. Publish the one-file production fix, focused regressions, complete evidence
   and a handoff. Leave gather/sequential-build integration separate.
