# Independent check plan (written before running anything for this round)

Reviewing Codex `825e752` (production: `ui/solver.py`, 68 lines added, 11
removed) and its evidence commit `c65d052` on
`codex/solver-progress-ux-2026-11-18`, against `main` at `bf5201c`.
Read so far: the production diff and the handoff. Not opened: Codex's test
harness (except, next, the few lines that show how to construct the widget),
its trace or its results.

This is a GUI change, not a numerical one. The review question is lifecycle:
can the bar ever end up in a wrong or stuck state.

## Concerns from reading the diff

 (a) Multi-frequency or dual-polarisation fixed-mesh runs. The determinate
     bar keeps the running maximum of callback percentages, capped at 99. If
     the solver's callback counter is per frequency (restarting at each one),
     the bar would reach 99 after the first frequency and sit there for the
     rest of a sweep. The handoff's real solves were single-frequency. This is
     the case I most expect to find a problem in.
 (b) Every exit of the finished/failed/cancelled handlers must leave the bar
     determinate (not animating) and the caption hidden. An activity bar left
     running after the job ends would be worse than the old behaviour.
 (c) An exception inside the finished handler after the "Preparing results"
     caption is shown.
 (d) Events arriving after a terminal state, in any order, must not change
     the bar or the status text.
 (e) The label on the bar ("Failed", "Canceled", "Partial") must not leak
     into the next job or into a boundary-density calculation, which shares
     the bar.

## Tests (own harness, real `SolverTab` under Qt offscreen)

T1. Invariant test with random event sequences. Drive the widget's own slots
    directly: start (each workflow kind), progress events with arbitrary
    percentages including resets, -1 and values above 100, telemetry events,
    then one terminal event (finished with each export outcome that can be
    reached without a dialog, error, cancel), then late events, then a new
    start. After every step assert:
    - determinate mode: value never decreases, never 100 before the terminal
      event;
    - activity mode: range is (0,0) and the caption is visible, only while
      the job is active;
    - after a terminal event: range is (0,100), caption hidden, and later
      progress or telemetry events change neither the bar nor the status;
    - a new start resets value, format and mode.
T2. Real solves through the GUI thread, recording every percentage the
    worker emits and every value the bar shows:
    - fixed mesh, one frequency (control);
    - fixed mesh, five frequencies (concern a);
    - fixed mesh, both polarisations if that is a separate pass.
    Report at what fraction of elapsed time the bar first shows 99.
    Acceptance for (a): the bar should not sit at its maximum for more than a
    small part of the run. If it reaches 99 early in a sweep, that is a
    usability defect to report even though nothing is numerically wrong.
T3. Run Codex's own harness unchanged and compare its 14 checks.

Not available here: Windows rendering of the activity indicator.
