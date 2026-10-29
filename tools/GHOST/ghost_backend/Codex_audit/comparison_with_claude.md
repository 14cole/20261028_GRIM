# Comparison of the Codex and Claude factorization audits

Date: October 28, 2026

The audits agree on the main decision: keep dense and compressed internally, simplify the user choices, and prioritize compressed capacity for larger geometries. Claude adds useful measured sweep totals and identifies storage failures omitted from the original Codex report. The main disagreement concerns the strength of the extrapolations and whether one airfoil trial justifies replacing the selection policy with fixed size thresholds.

This comparison checks [Claude's audit](../Claude_audit/2d_factorization_audit.md) and [Claude's comparison](../Claude_audit/comparison_with_codex.md) against [the trial CSV](../trials/airfoil_matrix_20261027_full/summary.csv), [the Codex audit](2d_factorization_audit.md), [the saved planner results](size_forecasts.json), and the current code. The shared 12-foot planner figures originate from the Codex forecast; their appearance in both audits is not independent validation. Neither audit includes completed 12-foot benchmark solves.

## Agreements that survive verification

| Finding | Assessment |
| --- | --- |
| Largest matched dense advantage is 14.5 seconds | Confirmed. |
| Dense is faster across all ten frequencies with adaptive meshing | Confirmed for all 60 matched adaptive rows, including repeated requested orders. |
| Compressed completes 64 configurations unavailable to dense | Confirmed. Adaptive factorization also completes those configurations by selecting compressed, so compressed is the enabling backend rather than literally the only successful mode label. |
| Explicit auto never wins a requested configuration outright | Confirmed in this trial. |
| Hierarchical should remain internally even if hidden as a routine option | Supported by shared code and its useful timing improvements. |
| No ordinary trial row has a successful reference-based accuracy certification | Confirmed. Dense agreement is not mesh convergence or independent physical validation. |
| The 12-foot model is substantially more expensive | Supported by its 12.13-fold geometric scale and current planner estimates. |

## Useful additions from Claude

Claude's sweep totals are reproducible. Summing the ten successful rows with adaptive meshing, requested P3, and grading disabled gives:

| Mode | Sum across 1 through 10 GHz |
| --- | ---: |
| Dense | 176.8 s |
| Hierarchical | 152.8 s |
| Compressed | 260.7 s |
| Adaptive factorization | 180.1 s |

Dense saves 83.9 seconds over compressed across that set; forced hierarchical saves another 24.0 seconds relative to dense. These are sums of recorded per-frequency solve times, not a newly measured integrated sweep with shared setup. They are more concrete than the original Codex report's hypothetical 100-job arithmetic example. Hierarchical beats dense in 37 of the 60 adaptive rows, also as Claude reports.

Claude correctly identified two retained-storage-cap failures missed in the original Codex narrative. Compressed's 180 trial rows break down into 156 successes, 2 rank-limit errors, 2 runtime storage-cap failures recorded as `memory_error`, and 20 forecast-based memory refusals. The storage-cap rows are `f08_local_p2_corners0_compressed` and `f08_global_p2_corners0_compressed`.

Claude also correctly flags a memory-budget discrepancy. Two successful compressed rows, local/global P3 with grading at 6 GHz, have sampled peaks of 10.130 and 10.176 GiB against the configured 8 GiB budget. These are about 10.88 and 10.93 decimal GB; the original Claude wording mixes GB and GiB. The discrepancy is material despite that unit correction. The Codex report has been updated to include it.

These findings make forecast calibration and retained-storage accounting higher priorities. They do not establish that lowering the planner's estimates across the board would be safe.

## Claims that need correction or qualification

### Auto factorization does not add a GPU switch

Claude calls `auto` factorization dense plus a GPU switch. The code distinguishes two settings: CPU factorization mode and the requested dense execution backend. In [the solver](../twod/solver.py), GPU consideration requires factorization to be `dense`; a non-dense factorization enters the CPU path. The separate dense-backend setting accepts `cpu`, `auto`, or `gpu`.

In [DenseFactor](../linalg/dense.py), both `dense` and `auto` can choose hierarchical factorization. Consolidating the factorization labels remains sensible, but the GPU explanation is incorrect.

There is also an update relevant to both audits: [the current run controls](../runs/controls.py) already expose four labels, not five. They map legacy `auto` to `dense`. The [2D options widget](../ui/twod_options.py) explicitly avoids displaying a fifth mode. The historical trial tests five names; the remaining UI simplification concerns forced Hierarchical and clearer Automatic naming. Saved `auto` should retain dense semantics, not silently become adaptive backend selection.

### The 12-foot estimates do not define a bounded range

Claude's roughly 14 GB measured-trend extrapolation and the planner's 132 GiB forecast at 10 GHz are two model outputs. Neither is a proven lower or upper bound, so the statements that they bracket the truth or that the real value is likely between them are unsupported.

The fitted exponent assumes continued behavior across changed electrical size, compression ranks, and possibly basis regimes. The planner explicitly includes rank growth with electrical cluster size in [compressed/hmatrix.py](../compressed/hmatrix.py). That is a stronger basis for explaining why capacity becomes difficult, but its forecasts are still estimates and can err in either direction.

Claude's comparison of a 3.9 GiB forecast to approximately 1.2 GiB measured RSS at original-size 10 GHz is suggestive, not a matched forecast-validation experiment. The saved forecast is from the current code with 361 assumed angles and initial P2/P3 candidates. Its 3.871 GiB maximum belongs to the P2 candidate; the P3 estimate is 2.457 GiB. The historical CSV identifies the final P3 result but does not establish identical code, angle count, and intermediate execution. A blanket 1.5-to-3-fold forecast correction is not established by that comparison.

Similarly, the 20 compressed refusals at estimated 8.15 through 12.84 GiB cannot be declared unnecessary merely because neighboring successful runs use less RAM. Those refused workloads have no measured completion peaks, and the successful over-budget examples show the opposite error can occur.

### Fourteen hours of LU is not the expected dense-mode runtime

Claude's 14-hour figure is a hypothetical cubic LU extrapolation. It is not a prediction of the normal `dense` mode, which can use hierarchical factorization above its default threshold and may fall back to LU. Under the evaluated 8 GiB budget, the 12-foot 10 GHz dense case is refused for memory before either algorithm runs.

The compressed estimate of 13 to 25 minutes is likewise an unverified extrapolation. It should not become a completion-time commitment or hardware purchasing assumption. A completed scaled run is needed to calibrate runtime.

### Dense still has a role at 12 feet

Claude's statement that the case for dense disappears at 12 feet is too broad. The shared adaptive forecast at 1 GHz admits both backends: about 5.6 GiB dense and 3.1 GiB compressed. Lower-frequency cases also fit dense. The practical conclusion depends on frequency, mesh, materials, available memory, and acceptance of refinement.

An approximately 17,700-unknown memory wall or 1.3 GHz crossover is a workload-specific approximation, not a universal limit. The planner includes assembly, factor, thread, right-hand-side, and geometry costs beyond a single constant times the square of the unknown count.

### A 6000-unknown threshold is a candidate experiment

Claude proposes lowering the LU-to-hierarchical threshold to about 6,000 unknowns and replacing backend selection with a dense-below-6,000-to-8,000 rule. This trial motivates investigating the crossover, but does not establish a universal threshold.

For example, the adaptive 10 GHz final system has 11,284 unknowns and dense still beats compressed by about 13 seconds. A fixed switch to compressed above 8,000 would sacrifice that measured advantage. The separate [numerical-methods notes](../../NUMERICAL_METHODS.md) report LU faster at 7,348 unknowns and near parity at 9,082 on another workload/thread setup. [The existing crossover hook](../linalg/hierarchical.py) already permits measured choices to override the default threshold.

The line count of the selection modules is not itself a measure of maintenance cost. Simplification may be worthwhile after checking several formulations and hardware configurations. Codex's recommendation was to preserve required selection behavior during consolidation, not to prohibit later simplification of its implementation.

## Combined recommendation

1. Keep dense and compressed internally. Use one clearly named Automatic default, with Dense and Compressed as advanced overrides. Retain forced hierarchical selection for diagnostics if useful. The legacy-auto UI consolidation already exists in this checkout.
2. Incorporate Claude's confirmed storage-cap failures and over-budget sampled peaks into the capacity work. Distinguish forecast refusal, runtime cap exhaustion, and observed process memory.
3. Diagnose rank-limit failures without assuming that 133 is a universal constant to increase. The sampled compression limit is derived from block dimensions and a configured maximum in [linalg/hierarchical.py](../linalg/hierarchical.py).
4. Benchmark a feasible 12-foot adaptive case at 1 GHz using both backends, identical settings, repeated timings, measured peak memory, and convergence checks. The current forecast admits that comparison; it does not guarantee success.
5. Calibrate memory estimates and LU/hierarchical crossovers against matched executions before changing global thresholds or reducing memory margins.
6. Preserve backward compatibility and numerical acceptance checks while simplifying interfaces or selection code.

Claude's audit improves the diagnosis of existing compressed limits and the presentation of sweep savings. Codex's forecast-based treatment is more defensible for current admission decisions, while actual large-model performance remains unmeasured. The combined evidence supports fewer routine choices and targeted capacity work, rather than deleting dense or treating fitted 12-foot timings as established performance.
