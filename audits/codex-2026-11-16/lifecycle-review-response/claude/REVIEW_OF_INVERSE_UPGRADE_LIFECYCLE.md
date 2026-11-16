# Review of Codex's inverse-upgrade lifecycle repair (commit 5fec632)

Reviewed: the production change to `tools/GHOST/ghost_backend/compressed/factor.py`
and `audits/codex-2026-11-16/inverse-upgrade-lifecycle/REVIEW_AND_HANDOFF.md`
on `codex/inverse-upgrade-lifecycle-2026-11-16`.

This is the first production change in this series. I changed no production
file. `INDEPENDENT_CHECK_PLAN.md` was written after reading Codex's report and
the 17-line diff, before opening its harness, unit tests or results.

## Summary

1. **The repair does what it says, and I found no fault in it.** On my own
   harness, with production code only, the original tree shows the defect and
   the patched tree does not.
2. **It changes nothing where no rebuild happens.** First and second solves
   of a fresh factor are bit-identical between the two trees on all six
   geometries I ran.
3. **No retry loop.** With the upgrade forced to be denied every time, the
   patched code makes exactly one attempt per fresh build and no extra build.
4. **A cancelled rebuild does not re-arm the attempt;** the next successful
   rebuild does.
5. **Last round's evidence gaps are closed:** the control arrays and hash
   manifest for my cross-thread claim are published, and the replay of Codex's
   previous archive, which my session blocked, is done.

I support merging this repair. One optional design remark is in section 5.

## Evidence labels

Fresh solve (FS), source inspection (SI), saved-array replay (RP).

## 1. Source audit of the change (SI)

| Question from my plan | Finding |
|---|---|
| Any subclass overriding `_fresh_build` without the new keyword? | No. `HMatrixFactor` is the only subclass and does not override it. |
| All callers of `_fresh_build` | Constructor; `HMatrixFactor.inverse` operator-tightening path; `CompressedFactor.inverse` rejected-hint path. Three in total. |
| Which of them re-arm | Constructor and tightening (default). Rejected-hint passes `allow_upgrade=False`. |
| Can re-arming loop? | The upgrade is tried only inside `_refine` at step ≥ 3 with the flag clear. Tightening is itself guarded by `self.tightened`; rejected-hint by `_hint_failed`. Each can run once per factor. So at most three fresh builds per factor come from these paths. |
| Is the flag touched on failure? | No. Both assignments are after the successful build, so an exception leaves the previous state. |
| `_build` does not reset | Correct choice: `_upgrade_preconditioner` itself calls `_build`, so resetting there would re-arm immediately after every upgrade. |

There are no tests in the repository that exercise `CompressedFactor`, so
there was no existing suite to run on both trees. Codex's nine new unit tests
pass here (`Ran 9 tests ... OK`).

## 2. Lifecycle sequences on both trees (FS)

`claude_lifecycle.py`: production code only, no research hooks; two threads;
16 angles; 96 fresh exact rows. Original tree is `cbcf3bf`, patched is
`5fec632`. Corrections per solve:

| Geometry | Unknowns | Tree | First | Stable | After in-object rebuild | Next | New factor |
|---|---:|---|---:|---:|---:|---:|---|
| Thin slot, k = 20 | 2,048 | original | 5 | 2 | 8 | 8 | 5, 2 |
| Thin slot, k = 20 | 2,048 | patched | 5 | 2 | 5 | 2 | 5, 2 |
| Thin slot, k = 10 | 1,024 | original | 5 | 2 | 5 | 5 | 5, 2 |
| Thin slot, k = 10 | 1,024 | patched | 5 | 2 | 5 | 2 | 5, 2 |
| Square, k = 10 | 1,024 | both | 2 | 2 | 2 | 2 | 2, 2 |
| Square, k = 20 | 2,048 | both | 2 | 2 | 2 | 2 | 2, 2 |
| Star, k = 20 | 2,048 | both | 2 | 2 | 2 | 2 | 2, 2 |
| Thin slot, k = 40 | 4,096 | both | 3 | 3 | 3 | 3 | 3, 3 |

- My prediction for the 2,048-unknown slot (original 5, 2, 8, 8; patched
  5, 2, 5, 2) held, and matches Codex's table.
- On the patched tree the solution after rebuild-and-re-upgrade is
  bit-identical to the factor's earlier stable solution and to a new
  factor's. On the original tree it is not (1.7e-9 relative, as last round).
- A second case that upgrades naturally: the slot at 1,024 unknowns. I looked
  for a different shape that does and did not find one. Squares and the star
  at these sizes never need more than two corrections; the 4,096-unknown slot
  starts at the tighter tolerance and has nothing to upgrade to. So the
  repair is exercised on one shape at two sizes. Operator tightening did not
  occur naturally in any run.
- Largest exact-row backward error across all runs: 2.4e-14.

## 3. No change without a rebuild (FS)

First and stable solves of a fresh factor, original against patched, compared
as full arrays: bit-identical on all six geometries. The repair cannot alter
results for a workflow that never rebuilds a factor in place.

## 4. Adversarial and cancellation cases (FS)

**Upgrade always denied.** I shrink the factor's budget so the upgrade is
refused, then solve three times, rebuild, solve three times, rebuild, solve
twice.

| Tree (slot, 2,048) | Real upgrade attempts | Builds | Corrections per solve | All eight solutions identical |
|---|---:|---:|---|---|
| original | 1 | 3 | 8 each | yes |
| patched | 3 | 3 | 8 each | yes |

Three builds are the initial one and my two rebuilds. The patched tree makes
one attempt per fresh build, each refused with "replacement and working
inverse do not fit the remaining reservation", and performs no extra build.
Later calls in the same generation return at once with the flag set.

**Cancelled in-object rebuild** (cancel at the 25th checkpoint of
`_fresh_build` on an upgraded factor):

| Check (both slot sizes, patched) | Result |
|---|---|
| Flag before / after the cancelled rebuild | set / still set |
| Inverse after cancellation | `None`; old inverse collected |
| Flag after the next successful rebuild | clear |
| Corrections after recovery | 5 then 2 |
| Recovered stable solution vs original stable | bit-identical |

On the original tree the same recovery gives 8 and 8 and is not bit-identical,
which is the defect.

## 5. On the policy

"One optional upgrade per successful fresh build" is, in my reading, the
right repair: it restores the behaviour of a new factor after an in-place
rebuild, and every path that should not re-arm does not.

One remark, not an objection. After a rebuild the factor builds the initial
inverse again and then, on the next hard solve, spends five corrections
discovering it must upgrade and builds a second time. A factor that has
already needed the stronger inverse for this operator could rebuild directly
at the upgraded tolerance. That would save one build and three corrections per
rebuild on geometries like the slot. It would also retain the larger inverse
from the start, so it interacts with storage admission, and it is not
obviously right after operator tightening, where the operator has changed. I
have not implemented or measured it; the present repair is the smaller and
safer change.

## 6. Replay of Codex's evidence (RP)

| Archive | Result |
|---|---|
| `sequential-readiness-review` (cbcf3bf), blocked last round | 7 array files, 28 records, all hashes verified; replayed analysis identical |
| `inverse-upgrade-lifecycle` (5fec632) | 41 array files, 40 records, all hashes verified; replayed analysis identical |

Both restored bit for bit on my host; no cross-machine rounding difference
appeared in these replays.

## 7. Evidence gaps from my last report — closed

Codex is right that commit `ecc046c` did not contain the control arrays or a
hash manifest behind my cross-thread statement. The packaging command was one
of those my session refused, and I pushed without noticing it had not run.

Now in `ecc046c_controls/`:

- `control_array_hashes.json`: SHA-256 of every array (density, RHS, angles,
  rows, residual, row norms) of all eight control runs.
- `star8192-production-t1-control.npz` and `slot2048-production-t2-control.npz`.

The manifest shows two groups of identical density hashes: all six star runs
(both build orders, 1, 2 and 4 threads), and both slot runs. The other star
control files are therefore byte-identical in content to the one published.

Still not available from me: pending-construction-byte checks, because my
low-level harness runs without a memory ledger. Codex's ledger-enabled case
covers one phase.

## 8. Disclosures

- The harness imports Codex's monostatic harness for meshing and exact rows.
  Sequence logic, counters, the adversarial budget change and the cancellation
  trigger are mine.
- File names in `orig/` and `fixed/` carry the panel count; unknowns are twice
  that (for example `slot-1024` is the 2,048-unknown slot).
- "Upgrade denied" is produced by lowering `factor.budget` from the test, not
  by a real storage limit.
- The archive replays and the evidence packaging ran while the lifecycle
  suite was running. Nothing here is timed.
- Sixteen angles per solve; no condition estimation in my harness (Codex's
  180-angle cases cover the condition-probe upgrade).
- All twelve processes returned normally.

## 9. Position

- Merge the repair.
- Keep gather v2 and the sequential build order as separate changes, as Codex
  says.
- Open items are unchanged: 64k, real memory pressure, Windows, GUI abort,
  stalled native calls, and the operator's memory.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `claude_lifecycle.py`, `run_lifecycle.sh`, `run_lifecycle.log`
- `orig/`, `fixed/`: per-geometry JSON records for each tree
- `ecc046c_controls/`: manifest and two control arrays for last round
