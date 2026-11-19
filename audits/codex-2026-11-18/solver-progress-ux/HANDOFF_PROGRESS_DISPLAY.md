# Solver progress display fix

Baseline: main `bf5201c26e0fa3ac98faf6363e52ab9e118d1a7c`.
Production-only commit: `825e752d342e6b857d41587f2a7e54b01be4a488`.
Only runtime file changed: `tools/GHOST/ghost_backend/ui/solver.py`.

This branch starts from accepted main. It does not include the withdrawn NumPy-F optimization or the experimental direct-BLAS implementation. Research findings inform subsequent work, but experimental branch contents are not automatically cumulative. The other 527 production/resource files, including native libraries, match the baseline exactly.

## User-visible behavior

Convergence callbacks can restart their local counters for another mesh, refinement or fallback. The old GUI displayed each local percentage as overall completion, causing backward jumps and early 100% readings.

- Both 2-D mesh-check workflows now use an activity indicator for the entire run, with the caption **Checking mesh convergence — additional passes may be needed.** BoR also uses activity mode because mode convergence is adaptive, with a corresponding mode/mesh caption. This deliberately makes no percentage or time-remaining claim when total work is unknown.
- Specified-mesh 2-D runs retain a percentage. It never decreases during the active run and is capped at 99 until result handling and automatic-export handling finish. It describes completed solve work, not a time estimate.
- Existing current-stage, elapsed-time and RAM messages remain available below the bar. No new buttons or solver options are added.
- Unknown callback totals are represented by `-1` on the private Qt worker signal and switch the GUI to activity mode for the remainder of the job.
- Cancellation, errors, partial results and subsequent jobs restore a determinate, stopped bar. Failed/canceled jobs show those labels. A partial result reports completed frequencies and stays below 100. A new invalid setup shows Failed instead of retaining the previous job's 100%.
- Queued progress/telemetry cannot overwrite cancellation or finishing status. A new solve resets the state. Boundary-density calculations reset the shared display before using it.
- A completed solve can still reach 100 when automatic export is declined, skipped or fails: its existing status/warning explains the export outcome and the numerical result remains available. The bar is held below 100, or in activity mode, while the export dialog/operation is pending.

## Implementation boundaries

The changes are confined to UI progress state, the private worker's unknown-total conversion, and the telemetry slot declaration (`Slot(object)`, matching its signal). No numerical assembly, factorization, convergence acceptance, precision, memory policy, solver selection or native build changes are made.

Rather than assigning invented weights to adaptive passes or freezing a percentage at 99 during repeated meshes, the UI uses Qt's built-in indeterminate range. Fixed-work notifications retain a per-run maximum. Successful result handling sets 100 only at its terminal exits.

## Validation performed

`check_progress.py` ran against the real PySide6 SolverTab under Linux Qt offscreen. All **14 integration/regression checks** passed; `verification.json` lists them.

Three actual GUI/QThread solves used a 0.1 m diameter PEC polygon approximating a circle, 64 fixed panels, 1 GHz, Dense, both polarizations and 180 monostatic angles:

| Workflow | Progress callbacks | Discrete quality gate | Mesh comparison |
|---|---:|---|---|
| Solve specified mesh | 371 | PASS | Not requested |
| Check specified mesh | 739 | PASS | PASS |
| Find converged mesh automatically | 739 | PASS | PASS; fixed-panel reference route |

The automatic workflow correctly retained the explicit panel discretization and used the reference comparison. It did not exercise a genuine adaptive refinement sequence. Repeated adaptive counter resets, unknown totals and BoR progress were checked with simulated callbacks on the real widgets. Other checks cover late events, cancel/error/restart, setup validation failure, successful export, declined export, stale export, export failure, partial results and reuse by density calculations.

The first harness run exposed a test-only serialization mistake: a compact sample table was converted to a string before reuse. The harness now keeps the real result object for callback tests and serializes sample tables as arrays of rows. No production sample handling was changed. The final full harness run passed.

`convergence-progress.png` is a synthetic convergence state rendered in the real Qt widget, over plots from a completed real solve. Its elapsed-time/RAM values are illustrative test inputs, not performance measurements.

Limits: Windows/PySide2 were not exercised. No numerical BoR solve was repeated, and no speed or RAM improvement is claimed. The final source was parsed and all baseline file identities checked; original CRLF line endings are preserved.

## Reproduce

Use a disposable copy of this audit directory with PySide6, NumPy, SciPy and Matplotlib available. Set `GRIM_ROOT` to a checkout of this branch. The script creates its own PEC geometry, recovery data, result records and screenshot in that directory.

```sh
GRIM_ROOT=/path/to/checkout OPENBLAS_NUM_THREADS=1 QT_QPA_PLATFORM=offscreen python check_progress.py
```

`evidence.tar.gz` contains the full final trace/metadata, all three result JSON files, the test log, geometry and screenshot. `evidence-manifest.json` gives archive and member SHA-256 hashes; the archive was read back and every member verified before publication. `verification.json` is the concise summary.

## Claude review request

Please independently check the lifecycle rather than rerunning backend optimization studies: convergence resets must remain activity-only; fixed progress must remain monotonic below 100; queued events must not replace cancel/finish status; all export/partial/error exits must stop the indicator; and a new solve or density calculation must reset it. Check the native Windows activity rendering if that environment is available. Review the production-only commit separately from the following audit/evidence commit.

Main is not modified by this branch. No experimental Dense change is being promoted with this UX fix.
