# Compressed default and explicit dense override

Date: 2026-10-29. Base revision: 5460aa2. This implements the user's preference for a simple, lower-memory default.

## Finding

None of the matched individual solves examined here demonstrates a five-minute dense saving. Dense remains useful as a reference and an explicit alternative, but the measured time savings do not justify making backend selection part of every ordinary run for this user's priorities.

The original `trials/airfoil_matrix_20261027_full/summary.csv` has 92 pairs where both requested modes completed successfully, matched by frequency, mesh strategy, polynomial order and corner grading. All pairs have equal panel counts. Dense wins 80 pairs; the median signed saving is 5.20 seconds. The maximum solve-wall saving is **14.54 seconds** at 9 GHz, adaptive mesh, requested P2, grading off (28.30 seconds dense versus 42.84 compressed). The maximum including process overhead is **15.11 seconds**. Neither metric has a five-minute saving.

This comparison excludes failed runs and higher-resolution reference rows. `status=ok` is operational success, not a new independent accuracy certificate. In particular, the maximum-saving pair has `reference_unavailable` in both accuracy fields. Requested orders in adaptive mode are not independent numerical-order experiments. The original accuracy flags and actual modes are retained in `airfoil_comparison.json`.

Recent repeated large-inlet studies reinforce the same practical conclusion:

| Study / case | Dense median seconds | Compressed median seconds | Dense saving | Dense / compressed peak RSS, GiB |
| --- | ---: | ---: | ---: | --- |
| Solver studies, ordinary metal at 15 GHz, 3 repeats | 86.40 | 125.31 | 38.91 s | 9.66–9.67 / 2.25–2.28 |
| Solver studies, narrow inlet at 15 GHz, 2 repeats | 114.59 | 140.33 | 25.74 s | 8.49–8.50 / 2.61–2.61 |
| Automatic-selection study, narrow inlet at 15 GHz, 2 repeats | 115.49 | 137.71 | 22.22 s | 8.49–8.55 / 2.58–2.58 |
| Automatic-selection study, dielectric inlet at 15 GHz, 2 repeats | 181.05 | 161.06 | **Compressed saves 19.98 s** | 5.82–5.85 / 3.99–3.99 |

Sources: `Codex_audit/solver_studies_20261029/summary.json` and `Codex_audit/automatic_selection_20261029/summary.json`, under their `comparisons` entries. Peak RSS is sampled process memory, not a guarantee of total machine demand. These are recorded trials, not reruns of large numerical benchmarks for this policy-only change.

It would be incorrect to claim dense can never save five minutes: longer sweeps or many repeated requests can accumulate that much saving. Summing all 92 airfoil comparisons gives 502 seconds, but that is a batch of different experimental configurations, not one solve or a representative production sweep. There is no evidence here to promise a five-minute saving for an unseen geometry. Complex 12-foot geometries at 15 GHz still need memory admission and convergence checks with either mode.

## Implemented behavior

- Fresh 2D monostatic GUI, local/HPC scripts, exploratory runs, efficient profiles and ordinary public `solver_method='auto'` calls default to compressed.
- The GUI offers Compressed and Dense. Enable **Override compressed solver (advanced)** and select Dense to override. Turning the override off returns to compressed.
- Adaptive mesh refinement and certification remain enabled. They refine the mesh without changing a fixed requested backend.
- Fixed compressed and dense requests neither read nor write persistent timing history. Their numerical execution does not invoke automatic backend selection or its cross-backend retries. A failure is reported rather than silently allocating dense storage.
- Dense remains available through the GUI override, script `FACTORIZATION = "dense"`, explicit API settings, or the existing launch override. Its internal factorization and numerical checks are preserved.
- Existing saved `adaptive` backend profiles and explicit legacy API requests retain their meaning for reproducibility. The GUI labels them **Automatic backend (legacy)** when loading one; fresh runs do not offer that choice. Historical `auto` factorization still means dense. These compatibility paths still contain the old selector; it has not been deleted from the repository.
- Low-level serialized version-1 defaults, explicit direct-method reference calls, bistatic capabilities and BoR policy remain unchanged. Non-double-precision automatic calls retain their supported dense path; explicitly requesting unsupported compressed precision still fails validation.
- Memory limits, storage admission, batching, numerical tolerances and request-local compressed inverse hints are retained. Parallel-frequency scheduling still uses resource forecasts to reserve memory for the fixed backend; forecasting does not authorize a backend change.

## Follow-up recommendation

Stop spending effort tuning the automatic dense/compressed chooser. Keep compatibility coverage until old profiles can be deliberately retired. Prioritize compressed memory scaling, inlet/coating accuracy and convergence studies. Dense is worth keeping as an explicit reference/fallback tool, without making its small measured speed gains drive the normal run policy.

## Validation

Validation results are saved beside this report. Coverage includes field equivalence across representative shapes/materials, certified P2/P3 mesh refinement in fixed compressed and dense modes, explicit launch overrides, compressed failure without dense retry, GUI controls and profile round trips, local/HPC execution and exports, fresh workers, frequency scheduling and legacy explicit automatic-mode compatibility. See `validation_summary.json` for the final outcomes and exact test files.
