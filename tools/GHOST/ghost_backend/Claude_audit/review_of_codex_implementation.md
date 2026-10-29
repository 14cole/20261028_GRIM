# Review of Codex's factorization implementation (2026-10-28)

Date: 2026-10-29
Reviewed: `Codex_audit/IMPLEMENTATION_FOR_CLAUDE.md`, `implementation_20261028/implementation.patch` (8 files), the edited files in the workspace, the validation summary and the 12 ft benchmark output. I read the code and results; I did not rerun the tests or the benchmark.

## Verdict

Safe to keep. I found no correctness bugs. The changes match what both audits recommended: one Automatic choice, Dense and Compressed as advanced overrides, `hierarchical` kept only for saved profiles, and legacy `auto` still meaning dense. Two small follow-ups are below, plus one tradeoff worth knowing about.

## File by file

| File | What changed | Review |
| --- | --- | --- |
| `runs/controls.py` | Labels now Automatic / Dense / Compressed (lower memory); `hierarchical` moved to a diagnostic label map | Correct. `run_control_options` still maps `auto` to dense, and unknown names still fail validation. |
| `ui/twod_options.py` | "Choose a solver manually (advanced)" checkbox; selector disabled until ticked; unticking returns to Automatic; a saved `hierarchical` profile shows a "(diagnostic)" entry | Correct. `set_value` blocks the selector's signal while rebuilding the list, but `_sync()` at the end still emits `changed`, so the run policy summary refreshes. Minor: after loading a `hierarchical` profile and unticking the override, the diagnostic entry stays in the list until the next load. Cosmetic only. |
| `run_local_monostatic.py`, `run_hpc_monostatic.py` | Comments only | Fine. |
| `compressed/memory.py` | H-matrix forecast now adds retained tile workers and retained compressed polynomial operators to the per-phase overhead | Correct and consistent with the tile-path forecast, which already counted both. Charged once per phase through `overhead`, not added to the payload cap (`hmatrix_factor.py` handles its cap separately). See the tradeoff below. |
| `compressed/operator.py` | Storage-cap check moved before any state change; error message now gives required and allowed bytes | Correct, and an improvement: the old code updated norms and counters, then raised. The exception type is still `MemoryError`, and the message still contains "retained-storage cap". I checked that no code matches the exact old string; the existing tests match on that substring and still pass. |
| `tests/test_run_controls.py`, `tests/test_factorization_audit_resources.py` | New GUI, forecast and atomic-rejection tests | Meaningful tests, not just smoke tests. The forecast test patches the module attributes that `hmatrix_forecast` imports at call time, so the patch takes effect. |

## Tradeoff: the forecast gets more conservative

The compressed forecast was already high. In Codex's own 12 ft benchmark it forecast 3.06 GiB and measured 1.34 GiB (2.3x). In the original trial it refused 20 compressed runs at 8.2 to 12.8 GiB. The new accounting is correct, but it only adds bytes. It applies when tile workers or a P2 operator are still alive as an adaptive run moves to a larger H-matrix mesh. On a 16 GB desktop with an 8 GiB budget, a few P2-to-P3 transitions that used to be admitted could now be refused. That is the safe direction. Improving the forecast's accuracy is still the most useful next fix.

## The 12 ft, 1 GHz benchmark

It checks out, and it agrees with my audit's extrapolation at that point:

| | Codex measured | My estimate |
| --- | --- | --- |
| Unknowns | 13,618 | about 13,000 |
| Dense time | 57.0 s median | about 1 min |
| Compressed time | 59.0 s median | about 1 min |
| Compressed peak RAM | 1.34 GiB | about 1.4 GB |
| Dense peak RAM | 5.92 GiB | 4.6 to 5.6 GiB |

One detail the summary leaves out: dense spent 25 to 26 s in factorization against 5.9 s for compressed. Dense's 2 s overall edge comes from faster assembly, not factorization. That is useful when deciding where to optimise compressed. Dense and compressed fields agree to about 3e-11, and both passed mesh convergence. That shows the two backends are consistent; it is still not an independent reference.

## Not done, and Codex's reasons are fair

- LU to HODLR crossover still 10,000 unknowns (I suggested about 6,000). Deferring until it is measured on more than one geometry is reasonable.
- The rank limit (133) and retained-storage cap are unchanged. The historical 6 GHz and 8 GHz failures are not claimed fixed.
- The planning code is not simplified, which matches the "references first" step in both audits.

## Follow-ups

1. The checkout has no Git repository, so the changes were applied directly to the working files with before/after snapshots. I would put the project under Git before the next round of edits, so changes like this can be reviewed and reverted cleanly.
2. Optional: clear the diagnostic entry when the manual override is unticked.
3. Next capacity work: tighten the compressed memory forecast, then revisit the rank and storage caps with a 12 ft 2 to 3 GHz case on HPC.
