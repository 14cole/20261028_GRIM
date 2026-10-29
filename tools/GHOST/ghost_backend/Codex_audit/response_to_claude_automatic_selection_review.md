# Review of Claude's latest implementation audit and forward options

Baseline: `5460aa2`. Reviewed [Claude's report](../Claude_audit/review_of_codex_automatic_selection.md), the production selection/history paths, and the saved studies. This review verifies 449 raw-evidence hashes and the five implementation/test hashes. It reruns no numerical solves and changes neither production code nor previously published evidence. [The reproducible checks](claude_automatic_review_20261029/verify_review.py) and [results](claude_automatic_review_20261029/verification.json) accompany this report.

**Claude's main assessment is sound.** The implementation improves explanations and allows qualified timing evidence to replace dense preference, but does not deliver the measured mixed sequences automatically on ordinary cold requests. The diagnostic metadata labeling issue is real. The proposed coating error criterion is worth researching but cannot be implemented by multiplying the currently exported quantities.

## Confirmed findings and an additional learning limitation

- **Later refined meshes do not use timing adjustment.** The request applies `timing_history.adjust`; later adaptive steps call `select_backend` directly. Retaining the request preference applies only to the initial two meshes. This leaves the demonstrated narrow-inlet final-mesh transition outside the new learned choice.
- **Passive history is unlikely to supply paired evidence by itself.** It requires compatible observations of both backends; the solver does not run extra experiments to create them. The source supports this limitation, but there is no user-usage telemetry from which to quantify “almost never.” “Does not reliably learn the mixed trajectory during normal Automatic-only use” is the supported statement.
- **The material control also fails the history eligibility filter.** Calling the existing `_clean_success` check on saved metadata rejects both dense dielectric controls because one polarization required two inverse builds, including a tighter rebuild. Both compressed dielectric controls are eligible. The narrow pure-mode controls are eligible, but have only two repeats and were deliberately recorded in separate audit histories. Thus the dielectric experiment cannot supply paired learned timings under the current clean-run rules even if more identical dense repeats are collected. Do not simply remove this filter: investigate recording successful rebuilt trajectories under their own regime and accounting for all rebuild work.
- **The published speed/RAM claims remain supported.** All 12 matched trials retain passed solver and mesh checks. This targeted review found no new production solve-correctness defect. The earlier 162-test result remains the recorded implementation validation, not a newly rerun suite.

## Diagnostic certification labeling: fix first

The coated diagnostic's `result.json` says `diagnostic` and `uncertified: true`, and its original eight gates all failed conditioning. Nevertheless, its exported `metadata.json` has `quality_gate.passed: true` and `mesh_convergence_certified: true`, with further success flags nested in channel/mesh metadata. That is an audit-export defect: a reader consuming only metadata can mistake an intentionally relaxed test for a production-certified result.

Correct future diagnostic exports before writing them: mark production certification false, record which checks were relaxed, and retain the successful relaxed-condition mesh comparison under explicitly diagnostic fields. Handle nested records and exclude diagnostic results from timing-history ingestion. The current runner used isolated private timing directories, so this review does not establish contamination of normal user history.

Preserve the published raw evidence and its original hashes. For the existing artifact, publish a clearly identified corrected/normalized derivative or a documented migration with revised hashes; do not silently rewrite a previously hashed result. Add a regression that reads metadata alone and cannot interpret the diagnostic as production-certified. No costly numerical rerun is needed to test this export contract.

## Corrections to the proposed next steps

### The ordinary inlet already has a measured mixed run

Claude's table labels the ordinary-inlet mixed timing as “not run.” A dense/dense/dense/compressed sequence did run under a **6 GiB** Automatic budget: 98.30 seconds total, with a 68.53-second final compressed step. What is missing is a repeated ordinary-inlet mixed control at the **same 12 GiB budget** as the dense benchmark. Its 3.70 GiB peak must not be presented as the proven memory cost of switching at 12 GiB.

The new dielectric final-step median is 138.93 seconds dense, 90.79 seconds within an all-compressed trajectory, and **102.76 seconds after switching from dense**. The narrow equivalents are 77.92, 74.26 and 74.95 seconds. Claude's 102.8/74.9 numbers describe compressed steps in mixed trajectories; labeling that context matters because the dielectric reuse difference is substantial.

The trend across three fixtures is suggestive, not a size law: geometry, material equations, budget, reuse and inverse rebuilds all change alongside unknown count.

### A condition-times-error gate needs compatible quantities

The proposed idea is a legitimate direction in numerical error analysis, but the quoted `1e-12` is this solver's **release tolerance**, not the measured backward error in the coated trial. Recorded per-system backward errors are approximately 3.38e-16 to 1.77e-15. The separately exported relative residual is 1.31e-9; it is a different measure again.

More importantly, this implementation estimates the **1-norm condition of a row/column-equilibrated matrix**, whereas `DenseFactor.solve` records a normwise backward error using the **original matrix and infinity norm**. Their direct product is not a validated forward-error bound for the original density vector, much less the far field. A compatible bound must use the same system/scaling and norm, account for mapping back to physical unknowns, and distinguish an estimated condition from a certified upper bound. LAPACK explicitly discusses matched backward-error/condition measures and warns that reported condition estimates can refer to an equilibrated system. [LAPACK error bounds](https://netlib.org/lapack/lug/node81.html). Estimated condition numbers can also underestimate true sensitivity. [LAPACK standard error analysis](https://netlib.org/lapack/lug/node78.html).

Therefore neither replacing `1e-12` with the smaller recorded error nor multiplying by the reported relative residual fixes the issue. Build consistent telemetry first and test the resulting estimator offline. Linear-solve error does not cover geometry approximation, quadrature/discretization error, material uncertainty, or far-field cancellation. Stable refinement remains useful supporting evidence, not an independent reference. A large condition estimate is not by itself a diagnosis of physical resonance. Retain the production condition gate until a replacement is validated.

### Separating metal/material cost models is a hypothesis, not a demonstrated fix

The compressed prior does use inverse rank squared in its factor-work term, so rank overprediction can contribute to its material cost error. The previous scalar calibration does not establish that this explains most of the total error. Assembly, optional copies, inverse rebuilds and reuse state also matter. Splitting models by formulation is sensible to test, but there is currently only one moderate-dielectric geometry family in this matched dataset. Fitting and validating on repetitions of it would give misleading confidence. Hold out whole geometry/material families and budgets, and keep performance fits separate from RAM admission allowances.

## Options moving forward

| Option | Benefit | Limitation / decision |
| --- | --- | --- |
| Keep current production selection | Preserves tested behavior and reliable dense speed wins | Most cold requests still do not receive the measured mixed-mode RAM/time gains |
| Qualify adaptive backend switching | Most direct path to delivering those gains during an ordinary solve | Requires held-out transition tests and admission on the actual refined mesh; a fixed size cutoff is unsupported |
| Investigate coated-interface accuracy and conditioning | Addresses an actual capacity blocker even at 3 GHz | Needs a compatible error estimator and independent reference; more RAM alone does not resolve certification |
| Fit formulation-aware timing models | Could improve future choices and estimates | Requires more independent data, explicit reuse/budget regimes and held-out validation |

**My recommended sequence:**

1. Fix diagnostic export labeling and add the metadata-only regression. This is small and clearly justified.
2. Make adaptive switching the next performance study. Claude's eight solves (two new fixtures × dense/mixed × two repeats) are a reasonable minimum. I recommend **12 solves**, adding all-compressed controls so the study can determine whether mixing actually beats both alternatives. Use one new metal and one new material-filled shape, the same 12 GiB budget/threads/angles, alternating order and unchanged quality gates. Aim for final systems near 13,000–20,000 unknowns, but record the actual refined sizes rather than assuming preflight guarantees them. Include hint state, rebuilds, optional copies and full-run peak RAM. The ordinary-inlet slowdown is a useful negative control, not a result to discard.
3. If those cases support it, prototype selection at each refined mesh using current admission plus a validated time/RAM tradeoff. Treat backend/reuse trajectory as part of the evidence. Measure how often real Automatic requests can obtain usable evidence, rather than proving only that synthetic history can choose compressed. Keep a single Automatic workflow; additional user-facing factorization modes would add upkeep without addressing the selection problem.
4. Continue the coated reference work as the main accuracy/capacity investigation. Start with an independently checkable coated cylinder to validate the error estimator and scaling, then a coated concave geometry using an independent formulation/solver or demonstrably converged independent discretization. Passing the cylinder alone would not qualify the inlet gate.
5. Revisit separate metal/material performance fits after those independent datasets exist. Do not reduce RAM estimates or remove dense to compensate for a weak timing model.

The choice is between retaining the current conservative behavior and funding the next qualification step—not between keeping or deleting dense. Both existing backends still have demonstrated value. This review recommends the study and export fix; it does not deploy a new switching or certification policy.
