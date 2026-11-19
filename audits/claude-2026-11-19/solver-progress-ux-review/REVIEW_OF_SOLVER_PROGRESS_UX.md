# Review of Codex's solver progress display fix (commits 825e752, c65d052)

Reviewed: production commit `825e752` (`tools/GHOST/ghost_backend/ui/solver.py`,
68 lines added, 11 removed) and its evidence commit `c65d052`
(`audits/codex-2026-11-18/solver-progress-ux/HANDOFF_PROGRESS_DISPLAY.md`) on
`codex/solver-progress-ux-2026-11-18`, against `main` at `bf5201c`.

I changed no production file. `INDEPENDENT_CHECK_PLAN.md` was written after
reading the diff and the handoff and before opening Codex's harness or
results. Tests run the real `SolverTab` under Qt offscreen on Linux.

## Summary

1. **The progress change is sound and I support merging it.** In 400
   randomized lifecycle sequences and eight real GUI solves I found no stuck,
   backward-moving or premature-100% state.
2. **My main concern did not materialise.** I expected multi-frequency
   fixed-mesh runs to sit at 99% after the first frequency. They do not: the
   solver's progress counter spans the whole sweep.
3. **Separate, pre-existing bug found while testing: the Cancel button is
   never enabled during a solve.** It is disabled for the entire run and
   clicking it does nothing. This is on `main` as well as on this branch, so it
   is not caused by Codex's change. It should be fixed before a release; the
   likely fix is a one-line reordering.

## 1. The progress change

### What it does (source inspection)

- Mesh-check workflows and BoR runs show Qt's activity indicator with a
  caption; fixed-mesh 2-D runs keep a percentage that only increases and is
  capped at 99 until results are handled.
- A callback with unknown total (now signalled as −1) switches a determinate
  run to activity mode for the rest of that job.
- Progress and telemetry events are ignored once the job is finishing,
  cancelled, or no longer marked as solving.
- Every terminal path calls one routine that restores a determinate, stopped
  bar and hides the caption.
- Nothing numerical is touched: only `ui/solver.py` differs from `main`.

Points I checked by reading and then tested:

| Question | Finding |
|---|---|
| Does every exit of the finished handler stop the indicator? | Yes: the two early returns (export cancelled; geometry or result changed) and the normal end each call the stop routine. Confirmed by test below. |
| Can the "Failed" / "Canceled" / "Partial" text leak into the next use of the bar? | No: a new solve and a boundary-density start both reset the format. |
| Is the solving flag set before the worker can emit? | Yes: the bar is started and the flag set before the thread is created; worker signals are queued. |
| Telemetry slot signature | Changed from `(int, str)` to `(object)`, matching the signal it is connected to. |

### Real GUI solves (fresh)

`claude_progress_real.py`: a 0.5 m PEC circle with 400 fixed panels, Dense,
180 angles, both polarisations, driven through `_run_solver` and the real
worker thread. Every progress event is recorded with a timestamp.

| Run | Seconds | Events | Counter resets seen | Bar only increased | Highest value before the end | Bar first at 99 after | Final | Quality gate |
|---|---:|---:|---:|---|---:|---:|---|---|
| Fixed mesh, 1 frequency | 1.3 | 371 | 0 | yes | 99 | 89% of the run | 100 | pass |
| Fixed mesh, 5 frequencies | 4.0 | 1,847 | 0 | yes | 99 | 88% | 100 | pass |
| Fixed mesh, 10 frequencies | 7.8 | 3,692 | 0 | yes | 99 | 89% | 100 | pass |
| Check mesh, 5 frequencies | 8.5 | 3,687 | 0 | activity mode throughout | — | — | 100 | pass |

- Concern (a) in my plan is refuted. The callback total covers all
  frequencies, so the percentage advances through the sweep and reaches 99
  only for the last tenth of the run, which is result handling.
- These are small, fast cases chosen to exercise the display. They are not
  timing measurements.

### Randomized lifecycle test (fresh)

`claude_progress_invariants.py`: one real solve supplies a genuine result
object; then 400 trials drive the widget's own slots directly. Each trial
starts a job (fixed-mesh, mesh-check or BoR), feeds 0–40 progress and
telemetry events with arbitrary values (including −1, values above 100, and
drops back towards zero), ends it one of seven ways, sends late events, and
starts again.

| Terminal path | Trials |
|---|---:|
| Error | 67 |
| Cancel | 73 |
| Finished, no export | 60 |
| Finished after an abort was requested | 48 |
| Cancel, then a late "finished" | 48 |
| Finished, export succeeds | 53 |
| Finished, export raises | 51 |

Invariants checked after every step, **0 violations in 400 trials**:

- fixed-mesh mode: the value never decreases and never reaches 100 before the
  job ends;
- activity mode: shown, with its caption, only while the job is active;
- after any terminal event: range back to 0–100, caption hidden, not marked
  as solving, expected text on the bar ("Failed", "Canceled" or a
  percentage), 100 only for a completed solve;
- late progress or telemetry events change neither the bar nor the status
  line;
- a boundary-density start after a failed job clears the label.

I confirmed separately that the export stubs are actually reached, and that a
real invalid setup after a completed job leaves the bar at 0 with "Failed".

### Codex's own harness

Run unchanged here: exit 0, "PASS 14 checks", three real GUI runs with the
same callback counts as reported (371 / 739 / 739). Its screenshot renders
the activity indicator and caption as described.

### Limits

- Linux, PySide6 6.12, Qt offscreen. I could not look at the native Windows
  activity indicator, nor PySide2.
- No real BoR solve; BoR was exercised through the widget's slots only.
- No genuinely adaptive mesh sequence occurred in my real runs (fixed panel
  counts), so counter resets were covered by the randomized test, not by a
  real solve.
- Export confirmation dialogs were not driven; the export call itself was
  stubbed to succeed and to raise.

## 2. Separate finding: Cancel is disabled during every solve

Not part of Codex's change. Present on `main` (`bf5201c`).

### Observation (fresh, both trees)

`claude_cancel_button.py`, real solve through the GUI thread, three
frequencies, with pending Qt events delivered between runs as they are in
interactive use:

| Check | `main` | This branch |
|---|---|---|
| Cancel button enabled at any sample during an undisturbed run | no (0 of 664) | no (0 of 701) |
| Button enabled when clicked 0.5 s into a run | no | no |
| Click cancelled the run | no — the solve completed and published its result | no |
| Calling the cancel handler directly | cancels correctly | cancels correctly |

Codex's screenshot of a run in progress also shows the Cancel button greyed.

### Cause (source inspection)

In `_run_solver`:

```
self._set_solving_state(True)      # applies button state; abort event is still None
abort_event = threading.Event()
self._abort_event = abort_event    # nothing re-applies the button state
```

`_apply_job_state` enables Cancel only when an abort event exists and is not
set. It is called when the solving flag is set, one line before the event is
created, and not again until the job ends. The boundary-density path does
these in the other order (event first, then state) and is not affected.

### Why it can look as if it works

If a second solve is started before the previous run's thread-finished signal
has been delivered, the previous run's event object is still attached, so the
button is enabled for that run. My first, cruder test did exactly this and
reported the button working. With events drained, as in normal use, it is
disabled every time.

### Suggested fix

Create and assign the abort event before `_set_solving_state(True)`, or call
`_apply_job_state()` after assigning it. I have not made or tested the change.
A regression test should start a real solve, deliver pending events, and
assert the button is enabled and that clicking it cancels.

I did not determine when this was introduced, or whether another route to
cancellation exists elsewhere in the application.

## 3. Recommendation

- Merge the progress change. It fixes the reported behaviour and my tests
  found no lifecycle defect.
- Fix the Cancel button separately and soon. A progress display that says
  "additional passes may be needed" beside a Cancel button that cannot be
  pressed is a poor combination for a long run.
- Windows rendering of the activity indicator still needs a look on the
  target machine.

## 4. Disclosures

- I read the part of Codex's harness that configures the widget for a real
  solve in order to construct mine; the invariant test, the multi-frequency
  runs and the Cancel test are my own design.
- All runs are single-threaded, small and fast. Nothing here is a performance
  measurement.
- Every process returned 0. The first version of the Cancel test gave a
  misleading "works" for the reason explained in section 2; the published
  script includes the event drain and both results files are from it.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `claude_progress_real.py`, `progress_real.json`
- `claude_progress_invariants.py`, `progress_invariants.json`
- `claude_cancel_button.py`, `cancel_button_main.json`,
  `cancel_button_patched.json`
- `codex_harness_rerun/`: log and check list from running Codex's harness
