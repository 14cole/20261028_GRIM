# Review of Codex's Cancel-button correction (commits c8c4755, 935d4d5)

Reviewed: production commit `c8c4755` (a three-line reordering in
`tools/GHOST/ghost_backend/ui/solver.py`) and its handoff
(`audits/codex-2026-11-18/solver-cancel-fix/HANDOFF_CANCEL_BUTTON.md`, head
`935d4d5`) on `codex/solver-cancel-fix-2026-11-18`. The branch sits on the
progress-display branch, so it carries both UI fixes; against `main`
(`bf5201c`) only `ui/solver.py` differs.

I changed no production file. `INDEPENDENT_CHECK_PLAN.md` was written first.
Tests use the real `SolverTab` under Qt offscreen on Linux, the real worker
thread, and real mouse clicks through `QTest`.

## Summary

**The correction works and I support merging both UI fixes together.**

- The Cancel button is now enabled from the start of every solve, in all 51
  runs of my timing test.
- 33 randomly timed real clicks each produced a clean cancellation; 18 runs
  completed normally. There were no inconsistent end states, no hangs and no
  stuck indicator.
- Clicking at the very end of a run, with the bar at 99%, also cancels
  cleanly in 12 of 12 trials.
- Last round's progress tests still pass unchanged on the corrected code.

## 1. The change (source inspection)

`_run_solver` now creates and assigns the abort event before it sets the
solving flag, so the button-state routine sees the event. The worker is
created and started after both, as before. Nothing else differs from the
progress-display branch. It is the reordering I suggested, and it matches the
order the boundary-density path already used.

## 2. Randomly timed cancellation (fresh)

`claude_cancel_timing.py`: 0.5 m PEC circle, 400 fixed panels, five
frequencies, 180 angles, Dense; about 4 s per undisturbed run. Pending Qt
events are delivered between runs unless stated. For each run the test
records whether a result was published and the final state of the bar, and
classifies the outcome as cancelled, completed or inconsistent.

| Group | Runs | Cancelled | Completed | Inconsistent |
|---|---:|---:|---:|---:|
| Undisturbed reference and final restart | 2 | 0 | 2 | 0 |
| Fixed click at 0.5 s, first run and after cleanup | 2 | 2 | 0 | 0 |
| Click immediately after start (one single, one double) | 2 | 2 | 0 | 0 |
| Fixed mesh, click at a random time | 24 | 15 | 9 | 0 |
| Fixed mesh, click aimed near the end | 8 | 0 | 8 | 0 |
| Mesh-check workflow, random time | 6 | 6 | 0 | 0 |
| Automatic workflow, random time | 4 | 4 | 0 | 0 |
| Started without delivering pending events | 2 | 1 | 1 | 0 |
| Double click mid-run | 1 | 1 | 0 | 0 |
| **Total** | **51** | **33** | **18** | **0** |

Checked in every run, with no failures:

- Cancel enabled at the start (51 of 51) and for 99.9% of samples while
  solving;
- after the job: bar determinate, caption hidden, not marked as solving,
  Cancel disabled, Run enabled, no dialog;
- cancelled runs publish no result and read "Canceled" below 100; completed
  runs publish a result and read 100.

Notes:

- All ten activity-mode runs (mesh-check and automatic) were cancelled while
  the indicator was animating, and each ended with a stopped, determinate bar.
- The run started without delivering pending events gets its own event and a
  working button. This is the situation that misled my first test last round.
- A click on the idle tab does nothing.
- The eight "near the end" runs and nine of the random ones completed because
  the click time fell after the run had already finished (later runs were
  faster than my reference). So that group did not test the end-of-run
  window; the next test does.

## 3. Clicks in the last moments of a run (fresh)

`claude_cancel_late.py` triggers the click from the bar's value instead of
the clock: once at 90, 95, 97 and 98, and eight times at 99.

| Bar value when clicked | Trials | Button enabled | Outcome | Clean end state |
|---:|---:|---|---|---|
| 90 | 1 | yes | cancelled | yes |
| 99 | 11 | yes | cancelled | yes |

(The 95, 97 and 98 triggers all fired with the bar already showing 99.)

Every one cancels: no result is published and the bar reads "Canceled" at
its last value. One consequence a user should know: pressing Cancel while
the bar shows 99% discards a solve whose numerical work may already be
complete. That is the existing cancellation policy (an abort request wins
over a late "finished"), and the status line still points to the recovery
folder for completed frequencies. I think it is the right behaviour; it is
worth a line in the user notes.

## 4. Regression of last round's tests on the corrected tree (fresh)

| Test | Result |
|---|---|
| 400-trial randomized lifecycle test | 0 violations |
| Real fixed-mesh runs, 1 / 5 / 10 frequencies | bar only increases, at most 99 before the end, first 99 at 85–89% of the run, final 100 |
| Real mesh-check run, 5 frequencies | activity mode throughout, final 100 |
| Last round's Cancel-button script | enabled in 645 of 645 samples; click cancels; bar reads "Canceled" |

Codex reports the same script failing on `main` and on the uncorrected
progress branch and passing on the corrected source, which matches my results
from last round and this one.

## 5. Limits

- Linux, PySide6, Qt offscreen. Windows rendering and PySide2 are untested.
- Small, fast Dense cases. Cancellation is cooperative: it takes effect at
  the solver's next checkpoint, and on a large case a long native
  factorization would delay it. I did not measure cancellation latency on a
  large problem.
- No real BoR run. No Compressed-backend cancellation through the GUI this
  round (the backend's cancellation was tested directly in earlier rounds).
- Export confirmation dialogs were not driven.

## 6. Recommendation

Merge the branch (`935d4d5`), which contains the progress-display fix and
this correction. Before release, look once at the activity indicator and the
Cancel button on the target Windows machine, and try cancelling one large
run there to see how long it takes to respond.

## 7. Disclosures

- I did not rerun Codex's `check_cancel.py` or unpack its evidence archive;
  my conclusions rest on my own runs.
- The outcome classification is made by my script from the published-result
  flag and the bar state.
- All processes returned 0.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `claude_cancel_timing.py`, `cancel_timing.json`, `cancel_timing.log`
- `claude_cancel_late.py`, `cancel_late.json`
- `regression_progress_invariants.json`, `regression_progress_real.json`,
  `regression_cancel_button.json` (last round's scripts, rerun unchanged)
