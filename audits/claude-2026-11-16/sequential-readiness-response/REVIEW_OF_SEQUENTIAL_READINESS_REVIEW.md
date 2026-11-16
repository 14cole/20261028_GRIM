# Review of Codex's sequential-readiness review (commit cbcf3bf)

Reviewed: `audits/codex-2026-11-16/sequential-readiness-review/REVIEW_AND_HANDOFF.md`
on `codex/sequential-readiness-review-2026-11-16`.
Research only; no production file is changed.

`INDEPENDENT_CHECK_PLAN.md` was written before any run, after reading only
Codex's report. I wrote and ran my own harness before opening Codex's
`run_readiness.py`.

## Summary

1. **Codex's two wording qualifications are accepted.** "Bit-identical"
   applies when the final inverse policy is matched; above the clean threshold
   solutions match while construction differs.
2. **Threaded construction is deterministic.** At 1, 2 and 4 threads, for both
   build orders, the 8,192-unknown star densities are bit-identical. The two
   slot runs agree bit for bit as well.
3. **Cancellation and recovery hold in every phase I targeted.** 48
   cancellations across five named phases, two build orders, three thread
   counts and two geometries. In all 48: the exception propagated, no worker
   thread survived, the abandoned inverse was collected, the operator was
   unchanged, and a rebuild solved correctly.
4. **The in-place solve, which I singled out as the likeliest to break, did
   not.** Cancelling inside it leaves nothing behind.
5. **One recovery was not bit-identical, and it is not a cancellation
   effect.** It reproduces with no cancellation at all and is a production
   behaviour worth a look: after a factor has upgraded its inverse once,
   rebuilding it in place returns to the weaker inverse and it never upgrades
   again.

## Evidence labels

Fresh solve (FS), fresh state check (FC), saved-array replay (RP), source
inspection (SI).

## 1. What I ran (FS, FC)

`claude_cancel.py`, one process per row. Gather v2 is applied to both build
orders, so the comparison isolates build order and threading, as in Codex's
suite. Sixteen monostatic angles, 96 freshly sampled exact coefficient rows.

| Geometry | Unknowns | Build order | Threads |
|---|---:|---|---|
| Dielectric star, k = 80 | 8,192 | production, corrected sequential | 1, 2, 4 |
| Thin slot, k = 20 | 2,048 | production, corrected sequential | 2 |

In each process: assemble the operator once; build a control factor and
solve; then, per phase, start a build, cancel it, check state, rebuild on the
same operator, solve and compare.

Cancellation is raised from the cooperative checkpoint (an
`InterruptedError` subclass) at a chosen call count while a named
construction guard is on the stack:

| Phase (guard label) | What is happening |
|---|---|
| sample products | threaded range products of the operator |
| leaf coefficients | diagonal coefficient query |
| projected QR | compression of an off-diagonal block |
| Woodbury correction | forming the correction system |
| inverse child product / (in place) | child solve; the in-place variant for sequential |

The first five use a new factor each time. A sixth case per process cancels a
rebuild inside the existing control factor (`_fresh_build`) and then rebuilds
it.

For the threaded phase with more than one thread, the trigger additionally
waits until at least one product task is in flight, counted by my own wrapper
around the product executor.

## 2. Determinism across threads (FS)

| Run | Product task threads seen | Density vs 1-thread production control | Exact-row backward error |
|---|---:|---|---:|
| star, production, 1 thread | 0 | reference | 4.2e-15 |
| star, production, 2 threads | 2 | bit-identical | 4.2e-15 |
| star, production, 4 threads | 4 | bit-identical | 4.2e-15 |
| star, sequential, 1 thread | 0 | bit-identical | 4.2e-15 |
| star, sequential, 2 threads | 2 | bit-identical | 4.2e-15 |
| star, sequential, 4 threads | 4 | bit-identical | 4.2e-15 |
| slot, production, 2 threads | 2 | reference (slot) | 2.8e-15 |
| slot, sequential, 2 threads | 2 | bit-identical | 2.8e-15 |

H1 holds. Assembly time fell from about 40 s to 25 s and 17 s with 2 and 4
threads, which confirms the threads were doing work; I make no timing claim
beyond that.

## 3. Cancellation and recovery (FC, FS)

All 48 cases (8 processes × 6):

| Check | Result |
|---|---|
| Cancellation exception reached the caller | 48 / 48 |
| Product-pool threads alive afterwards | 0 in all |
| Product tasks still in flight afterwards | 0 in all |
| Abandoned inverse object alive after garbage collection | 0 in all |
| Operator's accounted bytes unchanged | 48 / 48 |
| Factor's inverse left as `None` after an in-object cancelled rebuild | 8 / 8 |
| Rebuild and solve succeeded | 48 / 48 |
| Exact-row backward error of recovered solve | at most 4.2e-15 (star), 3.2e-15 (slot) |
| Recovered density bit-identical to control | 46 / 48 (see section 4) |

Worker actually active at cancellation, threaded phase, more than one thread:

| Run | Tasks in flight when cancelled | Started / finished at cancel | After join |
|---|---:|---|---|
| star, production, 2 and 4 threads | 1 | 31 / 30 | 31 / 31 |
| star, sequential, 2 and 4 threads | 1 | 14 / 13 | 14 / 14 |
| slot, production, 2 threads | 2 | 8 / 6 | 8 / 8 |
| slot, sequential, 2 threads | 1 | 20 / 19 | 20 / 20 |

- In every threaded case the cancellation was raised on the main thread while
  one or two worker tasks were running, and those tasks were joined before the
  exception surfaced. This matches the executor's documented contract and
  Codex's observation.
- The other phases are serial sections; no task was in flight there, as
  expected.
- H3 (in-place solve): cancelling at the fourth checkpoint inside the
  in-place child solve, so the array is partly overwritten, leaves no
  surviving object and recovery is bit-identical on the star.

What my harness could not check: `pending_construction_bytes`. The low-level
harness runs without a memory ledger (`memory_budget.current()` is `None`), so
there is no pending counter to read. Codex's suite ran with a ledger and
asserts it is zero; I have not independently confirmed that item.

## 4. The two non-identical recoveries (FS, SI)

Both are the slot, in-object rebuild case, one per build order. Maximum
per-angle density difference 1.7e-9 relative, backward error 3.2e-15: accurate,
but not the same bytes.

`claude_slot_attribution.py` repeats the sequence with **no cancellation**:

| Step | Inverse tolerance | Inverse MiB | Corrections in this solve | Density |
|---|---:|---:|---:|---|
| fresh factor | 1e-8 | 41.3 | — | — |
| first solve | upgrades to 1e-10 | 44.5 | 5 | reference |
| second solve, same factor | 1e-10 | 44.5 | 2 | bit-identical |
| `_fresh_build()`, no cancellation | back to 1e-8 | 41.3 | — | — |
| solve after rebuild | 1e-8, no upgrade | 41.3 | 8 | differs, 1.7e-9 |
| next solve | 1e-8, no upgrade | 41.3 | 8 | same as previous |
| a second fresh factor | upgrades to 1e-10 | 44.5 | 5 | bit-identical to reference |

Cause, from `compressed/factor.py`: `_upgrade_preconditioner` sets
`_upgrade_attempted` once per factor object and `_fresh_build` does not clear
it. A factor that has upgraded and is then rebuilt in place returns to the
initial tolerance and can never upgrade again, so every later solve pays eight
corrections instead of two.

- This is independent of build order and of cancellation.
- Results stay within all gates. It is a performance observation, not an
  accuracy one.
- I have not established how often production reaches it. `_fresh_build` is
  called on an existing factor after an operator rebuild
  (`hmatrix_factor.py`, tightened path) and in the retry path of
  `CompressedFactor.inverse`. Whether the one-shot flag is intended to survive
  those is a question for the owner of that code.
- It also means "rebuild inside the same factor" is not a clean recovery test
  on geometries that upgrade. The new-factor recoveries, which are the path
  Codex also tested, are bit-identical on the slot.

## 5. Replay of Codex's evidence

Not completed at the time of writing: the command runner in my session
stopped accepting commands after my own suite finished, before I could run
`unpack_evidence.py` and `analyze.py` on this archive. I read
`run_readiness.py` afterwards (SI): it requests cancellation once twelve
product tasks have started during a build and records the active count when
the checkpoint observes it, which is consistent with what I measured. I have
not verified Codex's archive hashes or its seven-case table this round, and
say so rather than imply it.

## 6. Position

- Agreed with Codex's integration recommendation: gather v2 and the corrected
  sequential build order, scoped to `HMatrixSystem`, with the query allowance
  limited to aligned diagonal queries.
- Added by this round: determinism to four threads at 8,192 unknowns, five
  cancellation phases, a second geometry, and in-object rebuilds.
- Still open: 64k, real memory pressure, Windows, GUI abort propagation, a
  stalled native call, larger threaded builds, and the operator's 1.9 GiB at
  32k.

## 7. Disclosures

- The harness imports Codex's monostatic harness for meshing and uses Codex's
  `corrected_builder.py` (the object under review). Checkpoint logic, task
  counting, state checks and comparisons are mine.
- Triggers are fixed call counts chosen in advance (6, 3, 3, 3, 4). On a
  512-unknown smoke test two phases did not reach their counts; I lowered
  those two counts before the real suite. The smoke output is not part of the
  evidence.
- The first version of the harness looked for worker threads calling the
  checkpoint and found none, because the executor calls it from the main
  thread. I replaced that probe with a counter of in-flight tasks before the
  real suite.
- Sixteen angles, not 180, to keep 56 solves affordable. No condition
  estimation in this harness; Codex's suite covers that.
- All eight processes returned 0. No timing claims.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `claude_cancel.py`, `claude_cancel_suite.json`, `run_cancel_suite.sh`,
  `claude_cancel_suite.log`, `gather_v2.py`
- `claude_slot_attribution.py`
- `out/`: per-run JSON records and logs, `slot_attribution.json`
