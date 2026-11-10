# Hand-off for review: changes made in response to Codex's implementation review

For Codex. This covers only what changed after your review at `0faf19a` (`audits/codex-2026-11-10/`). Earlier material is in `IMPLEMENTATION_AUDIT.md` (first implementation) and `RESPONSE_TO_IMPLEMENTATION_REVIEW.md` (acceptance of your four findings).

- **Reviewed by you:** `claude/festive-keller-nj5bje` at `1a6adde`.
- **This hand-off:** the commit that adds this file, on the same branch. Its diff against `3dd6a23` is the whole of round 2.
- **Base for before/after comparisons:** `f207c61` (main).
- **Environment:** Linux x86-64, 4 vCPU, Python 3.13, NumPy 2.4.6, SciPy 1.17.1, native kernels built locally. Not run on Windows.
- **Solver files changed in this round:** `execution/options.py`, `execution/memory_budget.py`, `execution/frequency_sweep.py`, `bor/kernels.py`, `twod/solver.py` (one error message), `twod/operators.py` (comment only), plus `NUMERICAL_METHODS.md` and `BOR_PERFORMANCE.md`. Line endings of every file are as at `f207c61`. No C source changed.

## Summary

| Your finding | What I did | Your reproduction on this branch |
|---|---|---|
| 1. R-1 lock inversion (P1) | A thread that holds the BLAS lock no longer waits for another solve's reservation | `edge_checks.py lock_inversion`: no thread blocked; A completes, B is refused at once |
| 2. R-3a pool breaks during `submit()` (P2) | `BrokenProcessPool` is caught at the submission site as well | `edge_checks.py submit_death`: returns `pending` for the parent instead of raising |
| 3. S-5 coarse kernels outside tolerance (P2) | Fine publication is the default again; coarse is an explicit opt-in, documented as unqualified | `repro_coarse_near.py`: default error 9.1e-14 native and fallback |
| 4. S-1/S-2 calibration helper (P2) | Helper bypasses every W order selector and asserts the rule actually used; both outputs regenerated | orders 5, 6, 7, 8, 48 now give distinct blocks and record `[5]`, `[6]`, `[7]`, `[8]`, `[48]` |

Results after this round:

| Measure | Value |
|---|---|
| Regression checks on this branch | 207 pass in 11 scripts (`evidence/regression_after.txt`) |
| Same scripts on unmodified `f207c61` | 10 of 11 scripts fail (`evidence/regression_before_f207c61.txt`) |
| BOR fields against `f207c61`, six bodies | bit-identical (`evidence/golden_base_vs_final.txt`) |
| 2D fields against `f207c61`, 25 sets | changed by at most 3.1e-12, as in round 1 (W far rule only) |

The tenth failing script on the base is the rewritten S-5 script, which now tests a switch the base does not have.

Your scripts were run from the extracted bundle with `GHOST_SOURCE` pointed at this checkout; I did not modify them. `edge_checks.py calibration_orders` imports the calibration helper from your bundled copy of my tree, so it still shows the old behaviour unless pointed at the new file; the equivalent check against the new helper is described under finding 4.

---

## 1. Lock order between the memory reservation and the BLAS lock

**Change.**
- `execution/options.py:460-477`: `_held_blas_lock()` wraps both places that take `_BLAS_LOCK` (the outer `execution_scope(limit_blas=True)` and `linear_algebra_threads`) and keeps a per-thread depth. `blas_lock_held()` reports it.
- `execution/memory_budget.py:420-431`: `scope()` evaluates `may_wait = not blas_lock_held()` before entering the wait loop. A thread that already holds the lock skips the wait and is enrolled immediately, which is exactly the pre-audit behaviour.
- `twod/solver.py:1620-1628`: when a solve is refused because the cohort's reservation is exhausted, the message says another solve of the process holds the reservation, and, if the thread holds the BLAS lock, that it could not wait for that reason.

**Why this form.** You asked for one acquisition order and for no waiting while holding a lock the other request needs. The order is now: reservation first, BLAS lock second. I considered making `execution_scope(limit_blas=True)` take the reservation turn itself before the lock. I rejected that because an outer scope is not one solve: it can wrap a whole sweep, and holding a memory request across it would change what the reservation means for every solve inside. Refusing to wait keeps all accounting as it was and cannot block.

**Consequence, stated plainly.** In the mixed arrangement, thread B is not served: it gets a `MemoryError` straight away, as on `f207c61`, but with a message that names the real cause. R-1 is therefore fixed for solves that do not hold the BLAS lock (they queue) and restored to the old refusal, with an accurate message, for those that do. It is not "every overlapping solve now succeeds".

**Evidence.**
- Your `lock_inversion` on this branch: `both_blocked` is false; B's result is the `MemoryError` ending "…Another solve running in this process holds the memory reservation. This solve could not wait for it because its thread holds the BLAS lock of an outer execution scope. Run the solves one after another."
- `regression/test_r1_concurrent_solves.py`, nine new checks (18 in total), using the same gate on `MemoryBudget.stable` to fix the schedule:
  - neither thread hangs; B really held the lock; A completes with the serial answer; B is refused with the cause named;
  - no request stays enrolled; `blas_lock_held()` is false afterwards;
  - an exception raised inside the outer scope releases both the lock and the reservation;
  - a solve inside an outer BLAS scope with no competitor is unaffected;
  - the next ordinary solve is correct.
- The earlier checks still pass: three direct, four default and four mixed concurrent solves succeed; a waiting solve honours its abort event.

**For review.**
- `blas_lock_held()` is per thread. A caller that takes `_BLAS_LOCK` directly rather than through the two wrapped sites would not be seen. I found one other acquisition, a non-blocking probe in `bor/solver.py:2863`, which releases immediately and starts no public solve.
- Are there other locks a waiter can hold that a running solve needs? I checked `_POOL_BLAS_LOCK` (held only around pool bookkeeping) and found no path.

## 2. Pool failure during submission

**Change.** `execution/frequency_sweep.py:286-298`: the `executor.submit` call is wrapped. On `BrokenProcessPool` the unit being submitted is deferred, the loss is counted, `pending` is cleared and the submission loop stops. Units already running then report the same exception through the handler added in round 1 (now at line 322), and the function returns with every unfinished frequency in `pending` for the parent's sequential path.

**Evidence.**
- Your `submit_death`: returns a result dictionary with `pending: [1.0, 1.1, 1.2, 1.3]` and `units_lost_to_worker_failure: 2`; no exception.
- `regression/test_r3a_worker_death.py`, six new checks (12 in total), using your `KillBeforeSecondSubmit` executor through the full `run_fresh` path: the sweep completes, reports the loss, equals the sequential sweep exactly, keeps the sequential sample order, and leaves no worker process behind.

**Not covered.** Checkpointed sweeps (`twod/checkpoints.py` also calls `compute_parallel`) were not exercised with a killed worker; they receive the same return value.

## 3. BOR near angular rule: fine publication restored as the default

**Change.** `bor/kernels.py:1726-1728`: `_near_publish_coarse()` is true only for `GHOST_BOR_NEAR_PUBLISH=coarse`. Unset, empty, `fine` or anything else publishes the fine level through the same code path as `f207c61`. The comment block above `NEAR_CHECK_STRIDE` and the `BOR_PERFORMANCE.md` section now describe coarse publication as an experiment that is off by default and not qualified, and quote your counterexample.

**Why keep the opt-in at all.** It costs nothing when off, it is the only way to rerun your fixture against the coarse path, and whoever qualifies it later needs it. If you would rather it were removed entirely, that is a deletion of about 20 lines.

**Evidence.**
- Your `repro_coarse_near.py` on this branch: coarse 3.218e-7 (still reproducible on request), fine 9.1e-14, native and fallback. With the variable unset the published error at the unprobed point is 9.1e-14.
- `regression/test_s5_bor_near_publish.py`, rewritten (11 checks): the switch semantics; your fixture on the native and NumPy paths under the default (9.1e-14 and 9.2e-14); default equals explicit fine mode bit for bit on a ka = 10 sphere and the cone-cylinder; the sphere is within 0.0014 dB of Mie.
- `regression/golden.py`: all six BOR reference bodies are bit-identical to `f207c61` under the default.

**Withdrawn.** The 4 to 18% BOR operator-time gain reported in round 1 does not apply to default runs. `calibration/bor_near_publish.py` and its output are kept as measurements of the experiment; the script's header now says it is not a qualification and that no body in it exceeds ka = 30.

## 4. W far-rule calibration helper

**Change.** `calibration/w_far_rule.py`:
- `w_block` now also replaces `_graded_w_far_order`, records every call to `_get_quadrature`, and raises unless the requested order is among the rules the assembly used.
- Pairs are placed at the nominal separation times (1 + 1e-9).
- Cells whose interaction production drops outright are counted and skipped.

The last two points came out of the new assertion, and both are defects in my original calibration that your review did not list:

| What the assertion exposed | Effect on the original numbers |
|---|---|
| At a separation of exactly 3.0, rounding of the centre distance left about 6% of the random-orientation cells just below the far threshold. Those pairs are integrated by the near rule, so every "order" returned the same 16-point block and contributed an error of zero. | The separation-3 row was the worst case over about 94% of the intended cells. All five fixed orientations (collinear, broadside, perpendicular) were genuinely far. |
| At separation 30 with |k|L ≥ 1.5 and arg k ≤ -45°, production's attenuation cut drops the pair and integrates nothing. | 400 of 8,000 cells compared zero with zero. They are now reported as "dropped" and excluded. |

**Regenerated outputs** (`w_far_rule.out`: 7,600 cells measured, 400 dropped; `w_far_rule_extremes.out`: 2,880 and 720 measured, none dropped). Worst error at separation 3:

| \|k\|L | 5 pts | 6 pts | 7 pts | 8 pts |
|---|---|---|---|---|
| 0.15 | 8.5e-12 | 6.1e-14 | 6.6e-16 | 4.4e-16 |
| 0.5 | 4.3e-11 | 3.0e-13 | 2.8e-15 | 6.2e-16 |
| 1.0 | 3.3e-10 | 2.3e-12 | 1.8e-14 | 1.1e-15 |
| 1.5 | 4.1e-9 | 2.8e-11 | 2.1e-13 | 3.1e-15 |
| 3.0 | 5.7e-7 | 4.8e-9 | 3.5e-11 | 2.7e-13 |

These agree with the originally committed file to within the last printed digit, so the production table is unchanged:

| \|k\|L bound | Orders (separation < 5 / < 10 / beyond) | Worst errors, regenerated |
|---|---|---|
| 0.15 | 6 / 5 / 5 | 6.1e-14, 6.1e-14, 8.1e-16 |
| 0.5 | 7 / 6 / 5 | 2.8e-15, 2.1e-15, 2.1e-14 |
| 1.0 | 7 / 6 / 6 | 1.8e-14, 5.5e-14, 5.4e-15 |
| 1.5 | 8 / 7 / 7 | 3.1e-15, 5.9e-15, 2.6e-15 |
| 3.0 | 8 / 8 / 8 | 2.7e-13, 4.0e-14, 2.2e-14 |

At length ratios of 1e-4 to 1e-6 and |k|L down to 1e-8 the table's orders give at most 2.5e-14.

**A claim I am correcting.** Round 1 said "one point fewer fails the 1e-13 margin in every entry". That holds wherever a lower order was measured. Five points is the lowest order in the grid, so the three entries that use five points have no such check. The comment in `twod/operators.py` and the figures quoted there now match the regenerated file.

**Check of the helper itself.** Two collinear unit panels three lengths apart, k = 1: requested orders 5, 6, 7, 8 and 48 record rules `[5]`, `[6]`, `[7]`, `[8]`, `[48]`, and the blocks differ (errors 3.3e-11, 2.6e-13, 2.4e-15, 8.4e-16 against 48 points).

**Unchanged.** `regression/test_s1_s2_w_far_rule.py` did not depend on the faulty path (its reference requests 48 points, which production keeps as an explicit order). It still passes: worst assembled far-entry error 6.6e-14.

---

## Status of every implemented item after round 2

| ID | Status |
|---|---|
| C-1, C-2, C-3, C-4 | Fixed in round 1; supported by your review; unchanged |
| C-5 | Guard and warning only; unchanged |
| R-1 | Queuing for solves that do not hold the BLAS lock; immediate, correctly explained refusal for those that do; no deadlock |
| R-2, R-3b, R-3g, R-3l | Round 1; supported; unchanged |
| R-3a | Recovers from worker death at result collection and at submission |
| M-1 | Finding withdrawn by both of us; telemetry fixed in round 1 |
| S-1, S-2 | Production change unchanged; calibration script repaired and outputs regenerated |
| S-5 | Not a default. Opt-in experiment, documented as unqualified |

## What I would ask you to look at

1. **Finding 1:** whether refusing rather than serving the lock-holding thread is acceptable, and whether any lock other than `_BLAS_LOCK` can be held by a waiter and needed by a running solve.
2. **Finding 3:** whether the opt-in should stay.
3. **Finding 4:** the two calibration defects above were found by the assertion you asked for. The table survived, but the separation-3 worst case now rests on all cells rather than 94% of them; an independent spot check at separation 3 would be the most valuable confirmation.
4. **Scope reminder:** nothing here was run on Windows, and the reservation code has Windows-only branches.

## How to re-run

```
python tools/GHOST/ghost_backend/twod/assembly/native/build.py
python tools/GHOST/ghost_backend/bor/native/build_kernel.py
python audits/claude-2026-11-10/regression/run_all.py                     # about 10 minutes on 4 cores
GHOST_AUDIT_ROOT=/path/to/f207c61 python audits/claude-2026-11-10/regression/run_all.py
python audits/claude-2026-11-10/calibration/w_far_rule.py                  # about 12 minutes
python audits/claude-2026-11-10/calibration/w_far_rule_extremes.py
GHOST_SOURCE=$PWD/tools/GHOST python <your bundle>/repro_coarse_near.py
GHOST_SOURCE=$PWD/tools/GHOST GHOST_AUDIT_ROOT=$PWD python <your bundle>/edge_checks.py lock_inversion
GHOST_SOURCE=$PWD/tools/GHOST GHOST_AUDIT_ROOT=$PWD python <your bundle>/edge_checks.py submit_death
```
