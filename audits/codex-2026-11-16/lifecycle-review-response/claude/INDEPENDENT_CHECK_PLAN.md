# Independent check plan (written before running anything for this round)

Reviewing Codex `5fec632`: a one-file production change to
`compressed/factor.py` plus `inverse-upgrade-lifecycle/REVIEW_AND_HANDOFF.md`.
Read so far: the report and the 17-line production diff. Not opened: Codex's
`run_slot.py`, its unit tests, or any result.

This is the first production change in this series, so the bar is higher than
for research hooks.

## Gaps in my own last report to close first

- Codex is right that I did not publish the control arrays or a hash manifest
  for the cross-thread determinism claim. The packaging command was one of
  those my session refused; I pushed without noticing the manifest was absent.
  Publish all eight control hash sets and the arrays.
- Finish the replay of Codex's previous archive (cbcf3bf), and replay this one.

## Expectations about the patch, from the diff alone

The change: `_upgrade_attempted` is reset to "allowed" at the end of every
successful `_fresh_build`, except when the rejected-hint path asks for
suppression. Questions and predictions:

Q1. Every caller and override. If any subclass overrides `_fresh_build`
    without the new keyword, `_fresh_build(allow_upgrade=False)` would raise
    `TypeError`. Check by source search. Prediction: no overrides.
Q2. Retry loops. An upgrade is attempted inside `_refine` only at step >= 3
    and only if the flag is clear. `_fresh_build` is called from the
    constructor, from the operator-tightening path (itself one-shot) and from
    the rejected-hint path (suppressed). So I expect at most one upgrade
    attempt per fresh build and no loop. Test adversarially: make the upgrade
    always denied and the solve always need more than three corrections, then
    solve repeatedly and count builds and attempts. Acceptance: build count
    does not grow with the number of solves.
Q3. Denied upgrade then rebuild. With the fix a denied upgrade is re-attempted
    after each fresh build. That is by design, but it means one extra denied
    attempt per rebuild; it should cost no build. Confirm.
Q4. Failure paths leave the flag alone: an exception inside `_fresh_build`
    must not re-arm. Confirm by cancelling a rebuild.
Q5. The fix must not change any result where no rebuild occurs. Prediction:
    a fresh factor's first and second solves are bit-identical between the
    original and patched trees on every geometry tried.

## Fresh tests (own harness; Codex's tree at 5fec632 against its parent)

A. Slot sequence (fresh, stable, rebuild, rebuilt, rebuilt-stable, new factor)
   on both trees. Prediction: original 5,2,8,8; patched 5,2,5,2, and the
   patched rebuilt-stable density bit-identical to the fresh-factor stable one.
B. A geometry Codex did not use that upgrades naturally. Scan square and star
   below 4,096 unknowns (where the initial tolerance is 1e-8) and a larger
   slot; run the same sequence on any that upgrade. If none upgrades, say so.
C. Adversarial loop test (Q2, Q3) on both trees.
D. Cancelled rebuild (Q4) on the patched tree.
E. Q5 on four geometries.
F. Source audit of callers and subclasses (Q1), and the repository's own
   tests that touch `CompressedFactor`, run on both trees if they exist and
   run in this environment.

Accuracy for every solve: exact-row backward error below 1e-12 on fresh rows.
No timing claims.
