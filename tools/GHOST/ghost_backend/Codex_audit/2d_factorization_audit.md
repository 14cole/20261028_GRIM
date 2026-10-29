# 2D factorization performance and maintenance audit

Date: October 28, 2026

Follow-up: [Comparison with Claude](comparison_with_claude.md) verifies additional storage failures, memory-budget discrepancies, and the current UI's existing legacy-auto mapping. The five names below refer to the historical benchmark; current run controls already expose four labels.

Dense saves only seconds over compressed in the supplied airfoil trial. The largest matched saving is 14.5 seconds, well below two minutes. Maintaining five routine user choices is difficult to justify from these results. Retain dense and compressed as internal backends, expose one Automatic default, and keep explicit overrides in advanced settings.

Compressed's strongest advantage is memory capacity. It completes 64 configurations that dense cannot fit within the trial's 8 GiB allocation budget. That advantage becomes more important for a uniformly enlarged 12-foot airfoil, although compressed also becomes expensive at high electrical size.

## Evidence and comparison method

The measurements come from [the original summary](../trials/airfoil_matrix_20261027_full/summary.csv), with settings in [the manifest](../trials/airfoil_matrix_20261027_full/manifest.json) and reference status in [the trial summary](../trials/airfoil_matrix_20261027_full/summary.json). The trial covers 1 through 10 GHz, four threads, and an 8 GiB solve budget.

Comparisons exclude failed runs and reference rows. Pairs match frequency, requested mesh strategy, requested basis order, and grading. All 92 successful dense/compressed pairs also match actual mesh strategy, actual basis order, and panel count. Timing uses `solve_wall_seconds`; overlapping assembly and solve stage timers must not be added together.

The trial contains 900 ordinary runs and 20 reference attempts. Adaptive meshing sometimes resolves different requested basis orders to the same final mesh, so the rows are not all independent workloads. Collapsing repeated adaptive requested orders by actual mesh and taking median timings leaves 52 comparable groups, with dense faster in 40; the conclusion is unchanged. These results do not establish statistical timing confidence across repeated benchmark campaigns.

## Measured benefits of dense and compressed

| Measure | Result |
| --- | ---: |
| Successful matched dense/compressed pairs | 92 |
| Pairs where dense is faster | 80 |
| Pairs where compressed is faster | 12 |
| Median saving among dense wins | 6.8 seconds |
| Largest dense saving | 14.5 seconds |
| Largest dense saving with fixed local/global meshes | 5.2 seconds |
| Largest compressed saving over dense | 11.5 seconds |
| Median dense/compressed sampled peak-memory ratio on matched runs | 2.8 times |
| Additional configurations completed by compressed while dense is refused for memory | 64 |

Dense's advantage is not confined to lower frequencies. With adaptive meshing, dense is faster in all 60 matched rows, including at 10 GHz. Electrical size, mesh density, and basis order are more useful predictors than frequency alone.

The following examples use grading, requested basis order 1, and adaptive meshing. Their resulting basis order is 3.

| Frequency | Dense solve | Compressed solve | Dense saving |
| --- | ---: | ---: | ---: |
| 1 GHz | 2.4 s | 5.4 s | 2.9 s |
| 5 GHz | 13.6 s | 23.2 s | 9.6 s |
| 10 GHz | 33.8 s | 46.6 s | 12.8 s |

These are modest waiting-time savings for individual jobs, despite substantial percentage improvements. They accumulate in repeated sweeps and optimization work. For example, a 10-second saving repeated across 100 otherwise comparable jobs amounts to about 17 minutes; this is an arithmetic illustration, not a measured batch result.

Fixed meshes show a different tradeoff. At 5 GHz, local P1 with grading takes 52.5 seconds in dense and 41.0 seconds in compressed. At 10 GHz, that fixed-mesh dense run is refused for memory while compressed completes in 109.7 seconds with sampled peak memory of approximately 2.75 GiB.

## Scaling the airfoil to 12 feet

The [input geometry](../trials/airfoil_matrix_20261027_full/input_airfoil.geo) spans x = -11.75 to 0.1217 inches, giving a length of 11.8717 inches. Scaling to 144 inches requires a factor of 12.1296866. The assessment assumes uniform scaling of both coordinates, including thicknesses and gaps, and unchanged material definitions. It concerns the 2D cross section, not a finite 3D wing or a change in span alone.

For unchanged constitutive properties, the electrical size depends on frequency times length. Thus 1 GHz on the enlarged airfoil corresponds approximately to 12.13 GHz on the original; 10 GHz corresponds to 121.3 GHz. Both exceed the original trial's maximum electrical size. Material dispersion or scaling only selected dimensions would change this correspondence. The underlying size/frequency relation is described in [Meep's discussion of scale-invariant electromagnetic units](https://meep.readthedocs.io/en/latest/Introduction/).

The following numbers are current-code resource forecasts, not measured solve times or completed accuracy certifications. Assumptions are four assembly and BLAS threads, 361 angles, an 8 GiB solve budget, automatic compressed storage, grading enabled, and a 100,000-panel limit. The 361-angle count is a planning assumption, not a verified angle count from the original trial. Adaptive forecasts include the initial P2/P3 solve/check candidates; later refinement may require more memory.

| Scaled geometry case | Dense estimated peak | Compressed estimated peak | Admission under 8 GiB |
| --- | ---: | ---: | --- |
| 1 GHz, fixed local P1 | 31.0 GiB | 5.3 GiB | Compressed only |
| 1 GHz, adaptive mesh | 5.6 GiB | 3.1 GiB | Both |
| 3 GHz, adaptive mesh | 40.2 GiB | 13.6 GiB | Neither |
| 10 GHz, adaptive mesh | 415 GiB | 132 GiB | Neither |

At 3 GHz, fixed local P1 is even more demanding: estimated peaks are 265.2 GiB dense and 35.1 GiB compressed. At 10 GHz, fixed local P1 exceeds the configured panel limit before memory admission. At lower frequencies, dense remains practical: the adaptive forecasts are approximately 1.1 GiB at 0.25 GHz and 2.4 GiB at 0.5 GHz.

Compression substantially extends capacity, but its ranks and costs can grow as the geometry becomes electrically larger. A constant compression ratio or a near-linear runtime extrapolation is not supported here. Adaptive meshing has a major effect on feasibility, and its accuracy must be accepted by the convergence checks.

Detailed forecasts are saved in [size_forecasts.json](size_forecasts.json). The [forecast procedure](../trials/factorization_review_20261028/forecast_size.py) generates meshes and resource estimates without assembling or factoring the electromagnetic system. Forecasts reflect the current checkout; they are not a recreation of the historical benchmark executable.

## Recommendations for the factorization modes

| Current mode | Recommendation | Evidence and rationale |
| --- | --- | --- |
| Compressed | Retain as a core backend and advanced memory-saving override | Completes 156 of 180 ordinary trial rows versus 92 for dense, with major capacity benefits for larger systems. |
| Dense | Retain internally and as an advanced diagnostic override | Faster for many small and adaptive problems; useful for reference comparisons and fallback. Current capability checks also allow dense in run types or precision settings unavailable to compressed. |
| Hierarchical | Remove from routine choices; retain the useful internal implementation | Largest observed saving over dense is 9.6 seconds. Hierarchical routines already participate in the dense and compressed implementations. |
| Auto | Consolidate into one Automatic choice | Never the fastest mode among successful modes for any requested configuration in this trial. Its largest win over dense is under 1 second. |
| Adaptive factorization | Retain its backend-selection function under the name Automatic | Provides memory-aware routing between dense and compressed. Keep the distinction from adaptive meshing clear. |

These are not five independent engines. In [linalg/dense.py](../linalg/dense.py), dense and auto can already select hierarchical factorization internally, with LU fallback. [linalg/hierarchical.py](../linalg/hierarchical.py) provides the default 10,000-unknown threshold and measured crossover hook. Compressed implementations also use hierarchical infrastructure, so removing a public option does not justify deleting all similarly named code.

The preferred interface is one Automatic default plus advanced Dense and Compressed overrides. Forced hierarchical selection can remain a developer diagnostic if needed. Preserve compatibility for saved configurations when consolidating names.

This is a qualitative maintenance recommendation. The audit does not measure developer hours or establish that removing any particular internal module would reduce upkeep. The clearest justified simplification is fewer public choices and less duplicated selection behavior, while preserving the numerical implementations that remain useful.

## Accuracy and reliability limits

No ordinary trial row has a successful reference-based accuracy certification: the required reference pair is unavailable at every frequency. All 92 comparable compressed rows pass the recorded dense-agreement check, but the additional 64 successful compressed rows have no successful dense comparison. Agreement between engines supports consistency, not mesh convergence or independent physical accuracy.

Compressed also has two rank-limit failures at 6 GHz, for local/global P1 without grading. Adaptive factorization repeats those two failures, yielding four error rows across the two modes. These failures demonstrate why compressed should not be described as universally reliable on the basis of this dataset.

The comparison with Claude identified two further compressed runtime failures: local/global P2 without grading at 8 GHz exceeded the retained-storage cap and were recorded as `memory_error`. Compressed's complete outcome split is 156 successes, 2 rank-limit errors, 2 runtime storage-cap failures, and 20 forecast-based memory refusals. Two successful compressed runs, local/global P3 with grading at 6 GHz, reached sampled peaks of 10.130 and 10.176 GiB despite the 8 GiB configured budget. Forecast calibration must account for underestimation as well as conservatism; neighboring successful cases do not prove that the refused cases would fit.

The 12-foot forecasts establish potential memory feasibility only. Actual memory, runtime, compression rank, and convergence require completed scaled-geometry runs. The benchmark's memory errors are admission decisions under its configured budget, not proof that the same modes cannot run with more memory.

## Suggested implementation sequence

1. Consolidate routine UI choices around Automatic and place explicit Dense and Compressed overrides in advanced settings.
2. Preserve old configuration names as supported aliases or migrate them with explicit mappings; retain forced hierarchical access for diagnostics if necessary.
3. Keep the automatic memory-admission checks, numerical acceptance gates, fallback behavior, and shared hierarchical code.
4. Before deleting internal solver paths, establish converged references and compare representative PEC, dielectric, mixed-material, and thin-gap cases, including a feasible scaled-airfoil case.
5. If 12-foot models at several GHz are a priority, focus development on compressed capacity, rank-limit robustness, and validated mesh reduction. The forecasts indicate that eliminating dense alone would not resolve their resource requirements.

For a workflow that tolerates an extra few seconds per solve, five exposed modes offer little demonstrated benefit. Two backends with one clear automatic selection policy retain the important speed, capacity, and diagnostic capabilities.
