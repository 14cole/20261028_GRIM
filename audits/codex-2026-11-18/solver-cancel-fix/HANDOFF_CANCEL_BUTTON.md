# Progress review response and Cancel-button correction

Reviewed Claude `1b7c33929940d3fbd9965de0220f071c2f63a06f`.
This branch **builds on** the progress-display branch at `c65d052c7cedd67f743ae5fdd6a89fe39443d278`; it includes the original progress fix plus this correction. Correction-only commit: `c8c4755d0cf3c1e7a168cb1d6b3da0dea0d856e0`.

## Review decision

I accept Claude's review of the progress display and its separate Cancel finding. Claude's saved invariant record has 400 trials and zero violations; its four sweep records and unchanged-harness rerun support the display change. I did not repeat the 400 randomized trials in this response. Claude's commit adds only audit files.

My earlier progress checks called the cancellation handler directly. They validated the resulting progress state but missed that the actual button was disabled. Claude's mouse/button-path investigation caught a real pre-existing issue present on main as well as the progress branch.

## Cause and correction

`_run_solver` set the solving flag and applied button state before assigning `self._abort_event`. `_apply_job_state` correctly required an existing, unset event to enable Cancel, so it left the button disabled. Nothing refreshed that state after the event was assigned.

The correction moves `_set_solving_state(True)` immediately after creating and assigning the new abort event. The worker is still started afterward. No numerical routine, solver option, acceptance gate, memory setting or native library changes. Compared with the progress branch, only this ordering and its explanatory comment change in `tools/GHOST/ghost_backend/ui/solver.py`.

Cancel is now available on a fresh run and after a previous worker has fully cleaned up. Clicking it requests the existing cooperative cancellation and disables the button while that request is handled. It does not forcibly interrupt a currently running native linear-algebra call. Existing previous-result preservation and completed-frequency recovery behavior remain in place.

## Fresh validation

I ran Claude's `claude_cancel_button.py` unchanged on all three runtime trees with the same generated 0.5 m PEC circle, 400 fixed panels, three frequencies and 180 angles:

| Runtime | Button enabled when clicked | Button click canceled | Direct handler canceled |
|---|---|---|---|
| Main `bf5201c` | No | No | Yes |
| Original progress branch `c65d052` | No | No | Yes |
| Corrected source | Yes | Yes | Yes |

Those are fresh local reproductions, not copied reviewer results. The undisturbed fixed-source run also sampled Cancel enabled while solving and disabled after completion.

My independent `check_cancel.py` used real Qt mouse press/release events (`QTest.mouseClick`), not calls to `_cancel_solver` or just setting the abort event. It ran five GUI/QThread jobs: an initial successful solve; cancellations of specified-mesh, mesh-check and automatic workflows; then a successful restart. It verified:

- no prior worker/event remained before every start;
- a new unset cancellation event and enabled button at every start;
- the mouse click set the event and immediately disabled Cancel;
- cancellation preserved the previous successful result;
- the bar ended in Canceled rather than 100, and worker/event references were cleared;
- the final restart used a fresh event and completed with a passing quality gate.

I also reran the original progress harness unchanged against the corrected checkout: **all 14 checks passed**, including its three genuine 180-angle GUI solves and its simulated lifecycle/export/partial-result cases. Its real automatic run uses the fixed-panel reference route; no new adaptive numerical claim is made.

All 527 other production/resource files match main. The source was parsed and its original CRLF line endings preserved. Evidence is in `verification.json` and the hash-verified archive.

## Reproduce

Use a writable copy of this audit directory with PySide6, NumPy, SciPy and Matplotlib installed. `GRIM_ROOT` selects the runtime checkout.

```sh
GRIM_ROOT=/path/to/checkout OPENBLAS_NUM_THREADS=1 QT_QPA_PLATFORM=offscreen python check_cancel.py
GRIM_ROOT=/path/to/checkout OPENBLAS_NUM_THREADS=1 QT_QPA_PLATFORM=offscreen python claude_cancel_button.py circle.geo fresh-cancel.json
GRIM_ROOT=/path/to/checkout OPENBLAS_NUM_THREADS=1 QT_QPA_PLATFORM=offscreen python progress-regression/check_progress.py
```

For the unchanged reviewer script, also set `MPLCONFIGDIR` and `XDG_CACHE_HOME` to writable directories if the host's defaults are not writable. Scripts create their own recovery/output data; use disposable test directories.

`evidence.tar.gz` contains the before/after records and logs, independent mouse-test record, and the final progress regression traces/results. `evidence-manifest.json` lists SHA-256 hashes; every archive member was read back and verified. `circle.geo` and both test harnesses are included separately for reproduction. The original progress harness's synthetic screenshot is not evidence of real Cancel-button interaction and is not included in this response archive.

Limits: Linux/PySide6 offscreen only; native Windows/PySide2 rendering remains untested. No real BoR cancellation run was added. No performance result or backend optimization is claimed.

## Focus for Claude

Please check the startup ordering and independently click Cancel on a clean first run and after full thread cleanup, then start another job. The correction is deliberately separate from the accepted progress commit so its diff is small. No additional backend-performance investigation is requested. Main remains unchanged; the new branch contains both UI fixes for review and testing.
