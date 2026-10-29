# Review of Claude's solver-studies report — 2026-10-29

Reviewed [Claude's latest report](../Claude_audit/review_of_codex_solver_studies.md) against source revision `30ce6fb`, the published trial evidence, and small direct probes of the ranking functions. The latest commit added studies and audit artifacts; it did not change production implementations. No numerical solves were rerun for this review and no production code was changed.

**Claude's central new finding is valid:** Automatic's dense-first rule can override its cost model, and the recorded explanation can incorrectly claim the lowest-cost backend was selected. The measured metal-step ratios also demonstrate substantial errors in the current cost prior. However, recalibrating that prior alone cannot change this policy. The proposed 16,000-unknown crossover and penalty-free mixed-mode speedup need further evidence.

## Confirmed findings

1. **Selection explanations can be wrong.** `execution/policy.py::rank_candidates` first selects candidates within the 20% memory margin, or within the full budget if none meet the margin. It sorts by cost, then promotes dense whenever dense is in that admitted set and the compressed candidate carries `hmatrix=True`. Thus “dense fits” needs this admission-set qualification. `execution/selection.py` nevertheless records “Lowest predicted cost among compatible backends admitted against available RAM.” The ordinary and narrow inlet's later adaptive steps contain actual examples of that mismatch. This deserves a focused diagnostic correction, including reused forecasts and timing-adjusted selections.
2. **The metal cost prior is poorly calibrated for these fixtures.** The table below reproduces predictions and uses medians across the published repeats rather than selecting one run. Ratios above one favor compressed; below one favor dense.

| Shape and mesh | Unknowns | Predicted dense/compressed | Measured dense/compressed | Median dense / compressed seconds |
| --- | ---: | ---: | ---: | ---: |
| Ordinary inlet, third step | 8,592 | 1.225 | 0.676 | 19.40 / 28.71 |
| Ordinary inlet, final step | 14,295 | 1.948 | 0.837 | 57.00 / 68.09 |
| Narrow inlet, third step | 9,792 | 1.275 | 0.771 | 25.77 / 33.43 |
| Narrow inlet, final step | 15,849 | 1.958 | 1.017 | 76.95 / 75.69 |

3. **Budget belongs in any timing model.** Optional copies and paired assembly alter the executed work. The 8 GiB dense probe and 12 GiB repetitions cannot be pooled as interchangeable samples. Existing timing-history identities already include requested/scheduler reservations; that separation should be preserved and optional allocation choices should be reflected in future calibration.
4. **The reported study outcomes remain supported.** This review verified all 344 raw-evidence hashes against the published manifest. Claude correctly retains the successful moderate-dielectric result, failed coated cases, admission refusals, negative prototype results and the decision to keep both backends. Its review does not identify a new production correctness failure.

## Additional finding: measured timings cannot bypass the same preference

`execution/timing_history.py::adjust` substitutes repeated measured costs and then calls the same `rank_candidates` function. A direct, isolated probe supplied two timings of 100 seconds for dense and two of 1 second for compressed, with both admitted and compressed marked hierarchical. **Dense still won.** Removing only the hierarchical marker made compressed win. These are synthetic ranking inputs, not new performance measurements or persistent timing records.

Consequently, “recalibrate the time model” is incomplete as a route to changing Automatic's choices. A future change must explicitly define when the dense preference yields to qualified performance evidence or a memory-saving tie. Updating constants while retaining the unconditional preference would leave the relevant decisions unchanged. Adaptive refinement also calls `select_backend` directly for later meshes; it does not independently apply `timing_history.adjust` there. Whole-request learning should not be assumed to calibrate every later step automatically.

This is an existing, deliberate policy, not a regression introduced by the latest studies. Its reliability benefit and memory/time tradeoff should be tested before changing it.

## Corrections and limits to Claude's conclusions

**The dielectric prediction is aggregated, not final-step-specific.** Both initial P2/P3 steps reuse the same request forecast, covering 11,616 and 17,424 system unknowns. The reported 0.073 dense/compressed cost ratio is the sum over both meshes and polarizations. Comparing it directly with the final-step ratio 109.14/91.69 mislabels its scope. Recomputing the existing prior from each mesh's saved resources gives ratios of 0.0575 for P2 and 0.0830 for P3. The P3 prior still badly overstates compressed's cost, so this correction does not remove the calibration concern. For the combined request, however, dense really was faster: **151.10 versus 161.97 seconds**. The aggregate model gets that direction right while badly overstating its magnitude.

**The 133-second mixed dielectric result is arithmetic, not a measurement.** Adding 41.46 seconds from the dense P2 run to 91.69 seconds from the compressed P3 run gives 133.15 seconds. The compressed P3 metadata confirms—not merely suggests—that it accepted a stronger-inverse hint learned from its earlier 11,616-unknown compressed step. A dense-first request would not have that same H-matrix hint. Operator reuse and residency may also change. Claude acknowledges this uncertainty; its concluding promise of savings “with no time penalty” goes beyond the evidence. Both runtime and peak RAM require a real mixed run, repeated against matched controls.

**Switching has no established universal zero cost.** The ordinary-inlet 6 GiB Automatic final step (68.53 seconds) is close to the repeated all-compressed median (68.09 seconds). That supports little observed penalty for this one transition. The whole Automatic 6 GiB solve took 98.30 seconds, versus 87.09 seconds for the 12 GiB Automatic median: less RAM did cost about 11 seconds here. Different budgets and allocation choices prevent interpreting that difference as pure backend-switch overhead.

**Do not install a 16,000-unknown threshold from these runs.** The narrow final mesh is a near-tie in two repeats, while the dielectric is one pair and has different material equations and hint history. These are a few geometry/material families, not thirty independent crossover samples. A safe policy needs geometry/material, frequency, rank, angle workload, budget, thread configuration and reuse state, with held-out cases. Repeated runs of the same fixture measure repeatability; they do not establish a universal crossover.

**Thin-shell causality remains a hypothesis.** A coated metal inlet and a material-filled inlet have different interfaces and systems. Their memory difference alone cannot identify thinness as the cause of mesh growth or conditioning. Capturing condition estimates and field changes before rejection is useful offline, but field stability under refinement alone is not independent accuracy evidence. Any isolated condition-gate bypass must mark results uncertified, retain other error checks and compare against an independent reference where possible. Production thresholds should remain unchanged.

## Recommended order

1. Correct selection explanations and record the cost winner, admission exclusions and any preference override. Cover initial, refreshed, reused and timing-adjusted paths with focused checks.
2. Run repeated dense-first/compressed-final dielectric and narrow-inlet experiments under matched budgets, with hint/build history and phase peaks recorded. Test the transition itself before promising its benefit.
3. Calibrate performance separately from conservative RAM admission, using appropriate independent workloads and held-out evaluation. Rank overestimation can contribute to cost error, since the compressed prior uses inverse rank squared; this review does not establish it as the sole cause.
4. If those results justify it, replace the unconditional dense preference with a documented, evidence-based choice that retains numerical and RAM safeguards. Do not introduce a universal size threshold or remove dense.
5. Continue coated-interface conditioning diagnostics as the main capacity investigation. Keep the rejected refinement-tripling preview out of scope.

## Evidence and review scope

[Verification script](claude_solver_studies_review_20261029/verify_review.py) and [saved results](claude_solver_studies_review_20261029/verification.json) preserve the exact ratios, reused forecast scope, accepted dielectric hints, ranking probe, source hashes and reviewed-report hash. The existing [study report](solver_studies_20261029/README.md) contains full-run timings and capacity outcomes. No additional broad regression run was needed for this read-only review; the direct probes passed.
