# Factorization implementation review for Claude

Date: October 28, 2026

The factorization controls now default to Automatic, with explicit Dense and Compressed choices behind an advanced manual override. Saved diagnostic settings retain their semantics. Hierarchical compressed memory forecasts now include retained workers and polynomial operators from earlier meshes, and tile storage-cap refusals report required and allowed bytes without partially modifying the operator.

The recommended 12-foot, 1 GHz comparison has also been completed: both backends passed quality and mesh-convergence checks in two isolated runs each. Dense saved about 2 seconds at the median, while compressed used about 4.4 times less sampled peak memory. This is measured evidence for one scaled case, replacing extrapolation at that operating point.

## Review package

| Artifact | Purpose |
| --- | --- |
| [Unified implementation patch](implementation_20261028/implementation.patch) | All application and regression-test edits from this implementation turn. |
| [Changed file hashes](implementation_20261028/changed_files.json) | Paths and before/after SHA256 hashes for eight implementation files. |
| [Original file snapshots](implementation_20261028/before) | Baseline files captured before edits; the checkout has no Git repository. |
| [Updated file snapshots](implementation_20261028/after) | Copies of the actual edited source and tests. |
| [Benchmark measurements](implementation_20261028/benchmark_measurements.json) | Compact timings, memory measurements, forecasts, and field comparisons. |
| [Full benchmark summary](implementation_20261028/benchmark_12ft/summary.json) | All four case results, requests, and comparison results. Each case directory also contains geometry, metadata, fields, and a worker log. |
| [Validation runner](implementation_20261028/run_validation.py) | Reproducible targeted checks with saved per-test reports. |
| [Benchmark runner](implementation_20261028/benchmark_12ft.py) | Reproducible isolated solves; refuses to overwrite existing case results. |
| [Automatic control preview](implementation_20261028/solver_controls_automatic.png) | Offscreen rendering of the actual widget with Automatic selected. |
| [Manual control preview](implementation_20261028/solver_controls_manual.png) | Offscreen rendering with the advanced override enabled. |

The patch covers production source and regression tests. Benchmark, validation, and capture utilities are separate review artifacts in this folder. No solver source changes are proposed solely inside the snapshots; the actual workspace files have been edited.

## Implemented changes

### Automatic selection and advanced overrides

[runs/controls.py](../runs/controls.py) and [ui/twod_options.py](../ui/twod_options.py) expose three ordinary labels: Automatic, Dense, and Compressed (lower memory). Automatic is initially selected. The solver selector is disabled until the user enables “Choose a solver manually (advanced).” Disabling that override returns the request to Automatic.

Automatic continues to serialize as `adaptive`, preserving the existing planner and saved-profile schema. Legacy `auto` still maps to dense in new run controls, while raw serialized execution profiles retain their original spelling through `validate_options`.

Explicit `hierarchical` remains valid through APIs and drivers. Loading that saved choice into the widget adds a clearly identified diagnostic entry and preserves its forced-factorization behavior. Fresh widgets do not offer it; loading an ordinary profile removes the diagnostic entry. There is no silent migration from forced hierarchical to dense, because their rejection and fallback semantics differ.

The [local driver](../run_local_monostatic.py) and [HPC driver](../run_hpc_monostatic.py) parameter comments document the three ordinary choices and retained legacy/diagnostic support. Run summaries distinguish Automatic backend selection from adaptive meshing.

### Retained memory in hierarchical forecasts

[compressed/memory.py](../compressed/memory.py) now includes existing tile-worker residency and retained compressed polynomial operators in every hierarchical forecast phase. A previous mesh can leave these run-owned allocations alive even after the next mesh switches to an H-matrix. The tile forecast already accounts for them; the hierarchical forecast previously omitted them.

The added evidence fields are `retained_worker_allowance_bytes` and `retained_polynomial_operator_bytes`. They contribute to total process overhead, not to the H-matrix operator's own retained payload or its storage cap. With neither resource resident, forecast values are unchanged. This accounts for live retained resources; it does not predict every future mesh transition during initial scheduling.

The regression test injects 512 MiB of retained workers and 64 MiB of retained polynomial data, verifies an exact 576 MiB increase in every phase and the overall peak, and checks that operator residency and payload limits do not change.

### Storage failures with useful evidence and intact state

[compressed/operator.py](../compressed/operator.py) now reports required bytes, allowed bytes, and system size when a retained-storage cap is exceeded. Tile failures also identify the tile coordinates.

Tile admission now checks the proposed payload before updating row/column norms, retained-byte counts, compression counters, or tile storage. A rejected tile therefore leaves the existing operator intact. A regression test rejects a tile one byte over budget, verifies the unchanged state, then admits the same tile at the exact required budget and checks its stored data and norms.

This improves failure diagnosis and admission behavior. It does not make an operator that exceeds its storage cap fit, and it does not weaken numerical acceptance limits.

## Completed scaled airfoil measurements

Geometry is the supplied 11.8717-inch airfoil uniformly scaled to 144 inches, including thicknesses and gaps, with unchanged materials. Each case uses 1 GHz, 361 angles from 0 through 360 degrees, both polarizations, adaptive P2/P3 certification, grading, double precision, four assembly/BLAS threads, an 8 GiB admission budget, and automatic compressed storage. Each repetition runs in a fresh process, in dense/compressed alternating order. Timings cover the certified solver call, excluding imports, preflight planning, and artifact writing.

| Backend | First solve | Second solve | Median | Sampled peak process RSS | Preflight peak forecast |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dense | 57.887 s | 56.132 s | 57.010 s | 5.917 to 5.918 GiB | 5.598 GiB |
| Compressed | 58.960 s | 59.096 s | 59.028 s | 1.341 to 1.349 GiB | 3.061 GiB |

Dense's median advantage is 2.018 seconds. The ratio of maximum observed peak RSS is 4.386. The final mesh has 2,990 panels with basis order 3; the preflight fine systems have 13,618 unknowns. All four results report passed quality gates and mesh-convergence certification.

The largest dense/compressed complex-field difference, normalized by the dense field's peak separately for each polarization, is 1.254e-11 for VV and 2.819e-11 for HH in both repetitions. All compared fields are finite. Both backends' mesh-convergence maximum normalized complex difference is approximately 2.078e-5, below the configured 0.002 acceptance limit.

The compressed forecast is conservative for this case, while the dense forecast is slightly below the sampled actual peak; both actual peaks remain below 8 GiB. This is not a basis for scaling all memory estimates downward. The 12-foot 3 GHz and 10 GHz cases remain forecasts from the audit, not completed solves. Two repetitions are a local consistency check, not a broad statistical performance study.

Mesh convergence applies to the supplied piecewise-linear geometry and solver acceptance checks. It is not an independent physical reference or certification of the drawn geometry's approximation to a smooth airfoil. The measured timing comparison also does not isolate a speed improvement caused by this patch; the numerical algorithms and thresholds are retained.

## Validation and review focus

The first targeted validation suite passed all 72 tests after moving temporary test outputs into the workspace. The suite covers the GUI defaults and override behavior, legacy and diagnostic settings, actual local/HPC export flows, compressed memory accounting, bounded workspaces, storage/cancellation behavior, polynomial spooling, measured crossovers, and admitted backend fallback.

The initial attempt's two driver-export failures were Windows permission errors while renaming temporary runtime directories. Those logs are preserved as [initial environment failures](implementation_20261028/validation_initial_temp_permission_failures.json); both tests pass with workspace-local temporary output. Subsequent timestamped `validation_results_*.json` files preserve each completed validation run, while `validation_results.json` contains the latest run.

The additional numerical suite passed 57 tests and 37 subtests, covering H-matrix operators and solves, PEC/IBC/dielectric/magnetic/coated/layered/two-body/thin-gap/acute/reentrant cases, compressed factor paths, and an analytic-cylinder check beyond dense admission. The combined result is **129 tests and 37 subtests passed**. Per-run counts are recorded in [the validation summary](implementation_20261028/validation_summary.json).

Claude should check these points:

1. Fresh and restored GUI states must never silently change a saved forced backend. Legacy `auto` must keep dense semantics.
2. Retained-worker and retained-polynomial bytes must be charged once per forecast phase, independently of the H-matrix payload cap.
3. A storage-cap rejection must leave operator state unchanged and retain the existing failure type for automatic retry handling.
4. Benchmark conclusions must remain scoped to the measured geometry, settings, and frequency; the 132 GiB high-frequency forecast is not replaced by a constant-ratio extrapolation.

## Remaining capacity work

The historical 6 GHz rank-limit and 8 GHz storage-cap cases are not claimed to be solved by this patch. The current baseline already contains the partial-final-batch rank fix, with regression coverage in `test_bounded_factor_workspaces.py`; it was preserved and tested. The value 133 is a block-dependent limit, not a global knob increased here.

The new accounting closes a specific omission, but does not establish the root cause of the historical 10.1 GiB sampled peaks. RSS sampling is not hard memory enforcement, and the admission forecast remains an estimate. H-matrix-to-tile fallback admission and larger fixed-mesh cases remain useful targets for a separate capacity investigation.

The default LU/hierarchical crossover remains 10,000 unknowns with the existing measured override hook. This implementation does not replace the selector with a universal 6,000-to-8,000-unknown rule, delete shared hierarchical code, lower quality gates, or increase storage/rank limits. The new measurements support the simpler interface and compressed capacity priority; they do not justify those numerical policy changes.
