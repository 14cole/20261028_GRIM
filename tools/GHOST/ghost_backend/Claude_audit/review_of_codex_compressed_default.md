# Review of Codex's compressed-default change (working tree on 5460aa2, 2026-10-29)

Reviewed:
- `Codex_audit/compressed_default_20261029/` (README, `airfoil_comparison.json`, `analyze_timings.py`, `validation_summary.json`)
- `Codex_audit/response_to_claude_automatic_selection_review.md`
- The uncommitted diff of the seven changed source files against `5460aa2`, plus the new `tests/test_compressed_defaults.py`

This change is **not on GitHub yet**: GitHub `main` is still at `5460aa2`. I read code and saved results only, and ran no solves.

## Verdict

The change does what you asked:
- Compressed is now the default everywhere a fresh 2D monostatic run starts: GUI, local and HPC scripts, exploratory runs, and the public API.
- Dense is available only by explicit choice.
- Adaptive refinement still runs.

The diff is small and clean. Old saved profiles keep their meaning. The new tests check the right things: no backend picker and no timing history in fixed modes, no silent dense retry, and the launch override.

Codex's timing analysis is correct. One gap needs fixing before this ships: default runs lose the automatic **angle-batch memory recovery** that was added two rounds ago. Details below.

## Numbers checked

I re-derived the airfoil comparison from `trials/airfoil_matrix_20261027_full/summary.csv`:

| Claim | My check | OK? |
| --- | --- | --- |
| 92 matched pairs, dense faster in 80 | 92 / 80 | Yes |
| Largest dense saving 14.54 s (9 GHz, adaptive, P2) | Matches | Yes |
| Median saving 5.20 s; total 502 s over all 92 | Matches | Yes |
| No five-minute saving in any single solve | Correct | Yes |

Two extra checks, both of which support the change:

- **Compressed never failed where dense succeeded.** In the original trial, compressed finished 156 cases and dense 92. Every compressed failure (22 memory refusals and 2 rank errors) also failed under dense and Automatic. So removing the dense fallback loses no case in that dataset.
- **Compressed never used more measured RAM than dense** in any of the 92 pairs, even on small meshes where its forecast was higher. The cost is time: compressed was a median 1.42x slower (worst 2.38x), which in absolute terms is the 5 to 15 s above.

## Issues

| # | Issue | Evidence | Fix |
| --- | --- | --- | --- |
| 1 | **Default runs lose automatic angle-batch recovery and idle-worker release.** In bb25908, when a run didn't fit, Automatic halved the angle batch (256 → 128 → …) and released idle tile workers before refusing. That logic, `_recover_memory_forecast`, is reached only through `select_backend`. Fixed modes now skip it: `options.py:598` runs selection only for `'adaptive'`, and the adaptive steps check `automatic_backend_requested()`. A fixed-compressed run that would have fit at a smaller batch is now refused by the solver's own memory gate (`twod/solver.py:2484`). | Code path. The 138 validation results include no batch-recovery test for the default path; the large-geometry resource tests still exercise Automatic only. | Run the same memory-only recovery (batch halving plus idle-worker release, no backend change) for fixed compressed. Add a regression where the default run fits only at a smaller batch. |
| 2 | **Stale comments in the driver scripts.** `run_local_monostatic.py` and `run_hpc_monostatic.py` still say "Automatic selects dense or compressed for the problem and memory budget" under the new compressed default. | Diff lines 34–35 of both scripts | Reword to say compressed is the default and dense is a manual override. |
| 3 | **Not committed.** It's a working-tree patch on top of `5460aa2`. | GitHub `main` = `5460aa2` | Commit once #1 is fixed. |
| 4 | **The coated-diagnostic metadata issue is still open.** Codex agrees it should be fixed first. | Codex response, "Diagnostic certification labeling" | Unchanged from my last review. |

## Codex's response to my last review

I accept its corrections:
- **Ordinary-inlet mixed run.** A mixed run *was* measured: the 6 GiB Automatic run, 98.3 s, compressed final step 68.5 s. I labelled it "not run". What's missing is a mixed run at the same 12 GiB budget.
- **My condition-number idea doesn't work as written.**
  - The 1e-12 I used is the solver's tolerance, not the measured backward error, which was about 3e-16 to 2e-15.
  - The condition estimate is the 1-norm of an equilibrated matrix, while the backward error uses the original matrix and the infinity norm.
  - Multiplying them is not a valid bound. A compatible estimator needs matched telemetry first.
- **Separate metal and material cost models are a hypothesis.** The matched dataset has only one material family.
- **New point from Codex:** the history filter rejects both dense dielectric controls, because they needed an inverse rebuild. So even repeated runs couldn't supply learned timings there.

These corrections are now mostly moot: the compressed default replaces further tuning of the Automatic picker. The "Decision options" section I added to `review_of_codex_automatic_selection.md` didn't reach your PC before Codex reviewed it; the copy there is the earlier version. Codex's own options table covered the same ground. I've marked that section as superseded.

## What this means in practice

- **Ordinary runs:** expect compressed to take about 5 to 15 s longer per solve on small to mid-size problems (median 1.4x), and up to 39 s longer at 15 GHz on the metal inlets. It uses about 70% less RAM on the large ones, and slightly less on small ones.
- **Material-filled 15 GHz inlet:** compressed is faster than dense (161 s vs 181 s at a 12 GiB budget).
- **When to pick dense:** as a cross-check, or when you want the fastest metal-only run and RAM is plentiful.

## Recommended next steps

1. Fix issue #1 (memory-only batch recovery for fixed compressed) and add the regression.
2. Fix the driver comments and the coated-diagnostic metadata labelling.
3. Commit and push. Keep the old Automatic code and its tests until the legacy profiles are retired, as Codex proposes.
4. Then turn to compressed memory scaling and coated-inlet conditioning, which both audits now rank as the main capacity limits.
