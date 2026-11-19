# Independent check plan (written before running anything for this round)

Reviewing Codex `c8c4755` (three-line reordering in `ui/solver.py`) and its
handoff `935d4d5` on `codex/solver-cancel-fix-2026-11-18`, which sits on top
of the progress-display branch. Read: the diff and the handoff.

The fix is the one I suggested, so the risk is not the fix itself but what a
now-pressable Cancel button exposes: paths that were unreachable from the
button before.

Predictions and tests (real `SolverTab`, Qt offscreen, real worker thread,
real mouse clicks through `QTest`):

1. Clean first run and run after full cleanup: button enabled throughout the
   solve; a click cancels. Expected to pass.
2. Click timing. Click at random points of the run, including immediately
   after start (before the worker has emitted anything) and at the very end
   (when the solve may already be finishing). For every outcome exactly one of
   two consistent states must result:
   - cancelled: no new result published, bar reads "Canceled", below 100;
   - completed: result published, bar at 100 with a percentage.
   Never a mixture (for example a published result with "Canceled", or a bar
   left in activity mode), never a hang, and the tab must accept a new solve.
   This is where I would expect a defect if there is one.
3. Double click and click-after-finish must be harmless.
4. Restart without draining pending events (the stale-event situation that
   misled my first test last round): the new run must get its own event and a
   working button.
5. Mesh-check workflow (activity mode): cancel must stop the animation.
6. Regression: my 400-trial lifecycle test and my real multi-frequency runs
   from last round, unchanged, on the corrected tree.

Acceptance: all of the above, with zero inconsistent end states over at least
30 randomly timed cancellations.
