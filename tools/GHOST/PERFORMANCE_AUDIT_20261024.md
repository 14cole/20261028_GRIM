# GHOST solver performance and maintenance audit

Audit date: 24 October 2026. This audit inspected the current working tree and ran bounded measurements. It made no changes to production solver code or numerical acceptance limits.

**Recommendation: retain dense solving, retain the distinct accuracy checks, and concentrate optimization on assembly, expensive retries, and consistent backend diagnostics.** There are real maintenance opportunities, but the inspected production paths already avoid several obvious forms of redundant matrix construction. Removing condition estimates is not the largest demonstrated performance opportunity.

## 1. Is building a dense matrix ever worthwhile?

**Yes. Keep it as a first-class backend.** On the measured cases, dense was 1.4–2.2 times faster than geometry-built compressed solving. Factors were reused across all 91 angles; neither backend rebuilt a factor for every angle.

| Fixture | Unknowns per polarization system | Dense, seconds | Compressed, seconds | Compressed / dense |
| --- | ---: | ---: | ---: | ---: |
| PEC circle | 256 | 0.2135 | 0.3149 | 1.47 |
| Lossy dielectric circle | 512 | 0.3384 | 0.5145 | 1.52 |
| Lossy dielectric circle | 1,024 | 0.7291 | 1.6082 | 2.21 |
| Dielectric coating with impedance core | 384 | 0.4459 | 0.6265 | 1.41 |

These are medians of three runs with condition estimation enabled. Both polarizations are included in each time. The maximum difference between compressed and dense complex fields, divided by the peak dense field magnitude, was at most 1.72e-11. This is agreement between implementations on the same discretization, not an independent physical accuracy certificate.

Dense has predictable numerical behavior and efficient factor reuse. Compression has setup, approximation, and refinement costs which can outweigh its savings on smaller systems. Its major advantage is limiting storage as problems grow.

Memory eventually changes the decision: a complex128 matrix alone needs `16*N*N` bytes. At 10,000 unknowns that is 1.49 GiB; at 20,000 it is 5.96 GiB; at 50,000 it is 37.25 GiB. Factors, region operators, workspaces, and concurrent jobs add to those figures. Count system unknowns, not just geometry panels.

There is also an important naming distinction. GHOST's dense route can assemble the full matrix and then use a hierarchical factor. Its default hierarchical threshold is 10,000 unknowns, subject to overrides and measured crossover selection. That reduces factor storage/work but does not eliminate the original dense matrix. The compressed route builds a streamed operator without that global dense allocation. See [dense factor management](ghost_backend/linalg/dense.py), [hierarchical selection](ghost_backend/linalg/hierarchical.py), and [compressed factors](ghost_backend/compressed/factor.py).

**Concrete issue:** `execution/policy.py::rank_candidates` first sorts by predicted cost, then forces dense first whenever dense fits and the compressed candidate is marked `hmatrix`. However, `execution/selection.py` describes the choice as the lowest predicted cost. The conservative preference may be reasonable, but the explanation is inaccurate whenever that override changes the order.

Recommendation: keep the conservative policy initially, record its actual reason, and evaluate a measured crossover on representative large workloads before changing selection. Benefit: clearer decisions and potentially better large-case performance. Cost: a trustworthy crossover requires multiple geometries, frequencies, memory budgets, and machines. These small benchmarks do not establish it.

## 2. Are there too many convergence checks?

**There are many layers, but most check different errors.** A tiny algebraic residual does not establish mesh convergence, quadrature accuracy, or sufficient BoR modes.

| Check | What it protects against | Recommendation |
| --- | --- | --- |
| Linear residual and backward error | Failure to solve the assembled equations accurately | Keep; compute from the same residual where possible |
| Compression error bounds and refined residuals | An approximate operator/factor giving an inaccurate solution | Keep original-coefficient acceptance |
| BoR modal tail | Truncating the azimuthal expansion too early | Keep, including the minimum physically motivated mode horizon |
| Near/singular quadrature checks | Inaccurate integration, particularly close boundaries and junctions | Keep |
| Mesh / polynomial refinement comparison | A discretization too coarse for the requested fields | Keep for certified results |
| Condition estimate | Sensitivity of the linear system | Keep as a separate diagnostic/gate, not a mesh certificate |

The current implementations already reuse work. Dense factors reuse residuals returned by refined solves. Relative residual and backward error share a residual product. Adaptive 2D uses polynomial-pair and moment caches, carries the previous fine solution forward, and can finish certification from the existing pair. BoR has preparation and mode-resume machinery for cap extensions. The optional BoR same-mesh quadrature comparison performs two solves, but defaults to **off**; it is not an unconditional extra production solve. See [2D adaptivity](ghost_backend/twod/adaptivity.py), [BoR mode sweep](ghost_backend/bor/solver.py), and [optional quadrature comparison](ghost_backend/bor/quadrature.py).

Two areas deserve review:

* **Internal compressed refinement is stricter than final acceptance.** `compressed/factor.py` targets 3e-15 for the compressed-operator residual, while the physical backward-error limit is 1e-12. Even condition probes admitted with a looser physical error bound pass through that same inner target. This leaves a margin for operator approximation error, so the two numbers cannot simply be equated.
* **Adaptive candidates use a tighter policy than some user requests.** `twod/adaptivity.py` caps candidate complex RMS change at 0.1% and maximum change at 0.2%, alongside dB/phase caps, to limit error introduced by coarsening. It also enables condition estimates for all candidate solves. Failed adaptive attempts followed by a reference fallback can therefore cost substantially more than one certified pair. This is deliberate behavior worth making visible in timing and progress reports.

I tested temporary, in-process inner targets of 1e-13 and 3e-13 against the current 3e-15 target. Eighteen additional runs used two lossy fixtures, three targets, and three trials. Production files were untouched and the physical acceptance checks stayed enabled. Refinement counts fell, but median total time improved only about 0–3%; one comparison became slightly slower. For the 1,024-unknown case, peak-normalized field disagreement with dense increased from 3.45e-14 to about 1.1e-9. All tested variants passed the existing physical gates.

**Do not change the tolerance globally on this evidence.** A future optimization could allocate inner accuracy from the remaining physical error budget, especially for condition probes. The benefit must be demonstrated on difficult, large, resonant, and close-interface cases. The present small-case speed gain is unconvincing.

For adaptive certification, report elapsed time for candidate solves, rejected attempts, and fallback separately. Then evaluate whether inexpensive rejection tests can avoid expensive diagnostics on candidates that will already fail. Accepted certified results should retain their full checks. The tradeoff is that rearranging validation can change failure timing and must preserve which results are publishable.

## 3. Which methods could be trimmed?

Source inspection does not establish how frequently users invoke a method. The following are candidates for consolidation or deprecation, not evidence that physical capabilities are unused.

| Candidate | Benefit of trimming or isolating it | Reason for caution |
| --- | --- | --- |
| No-SciPy fallback in dense solving | Removes a secondary path that can refactor for each batch and use a more expensive condition calculation | Packaged GHOST requires SciPy, but legacy standalone support must be resolved before removal |
| Optional CuPy dense route | Reduces separate transfer, solve, fallback, and validation logic | GPU was not benchmarked; real GPU workloads could justify keeping it |
| Explicit diagnostic EFIE/MFIE choices in the ordinary interface | Simplifies the common workflow | Useful independent formulations for numerical diagnosis; EFIE-related capabilities are needed for supported open-surface/sheet cases |
| Explicit BoR table assembly alongside automatic streaming | Reduces the number of ordinary controls | Keep a reference/validation route and demonstrate workload coverage before deleting an implementation |

The GPU route transfers the matrix and RHS for a solve and calls `cp.linalg.solve`; condition-enabled requests dispatch to CPU. It therefore has a narrower role than the existence of a GPU option suggests. Isolate it as an advanced backend until its supported use cases and benchmarks justify broader exposure.

Keep dense reference solves, compressed large-problem support, mixed-precision fallback safeguards, mirror-symmetry acceleration, and material-specific formulations. Their roles differ. Fewer visible choices can be achieved without deleting useful numerical coverage.

There is definite small dead-code cleanup available now:

* `bor/solver.py`, around line 5892: `table_far_double` is calculated but never consumed. It invokes several storage estimators; it does **not** allocate the table its name describes.
* `bor/streaming.py`, around lines 2628 and 2775: unused `efie_orders` scalar calculations.
* `twod/solver.py::_solve_dense_system`, around lines 650 and 744: later `condition_diagnostics is not None` branches are unreachable because the earlier CPU dispatch already returns for that case.

These are worthwhile readability improvements with negligible expected end-to-end speedup. They should not be presented as a major numerical optimization.

## 4. Are unused matrices or unnecessary steps slowing calculations?

**I did not find a large, routinely built and wholly unused matrix in the main paths inspected.** This is a scoped finding, not a proof covering every formulation.

Several apparent duplication concerns are already addressed:

* BoR `_B_T` and `_B_D` point matrices start as `None` and are constructed lazily.
* BoR preparation requests the needed EFIE/MFIE/IBC families. Cross-family storage and replaced symbolic blocks have demand-driven paths.
* Original dense coefficients retained beside an LU factor are used to validate physical residuals. Removing them would remove that validation; disk spooling is already available when memory is tight.
* Factorization is reused across angle batches. BoR uses separate modal systems, so factorization per mode is necessary.
* RHS compression has a cost policy and fallback; not every sweep blindly pays for a full compression attempt.

In the measured cases, operator construction accounted for approximately **63–79% of the internally profiled solve time**. Condition estimation accounted for much less. This supports prioritizing assembly, operator reuse, and the number of full candidate solves over deleting scalar checks. It does not imply that all assembly work is wasteful, or that assembly will dominate much larger problems where factorization costs grow.

One concrete optimization opportunity is the BoR condition-estimation interface: hierarchical/mirror and compressed wrappers supply `matvec`/`rmatvec` but omit block `matmat`/`rmatmat`, unlike the 2D estimator. Supplying bounded block operations may amortize repeated work across probe vectors. This is source-confirmed missing batching, but its speed benefit remains unmeasured.

## 5. Is calculating condition number worthwhile?

**Yes for trusted results and numerical diagnosis; optional for exploratory runs.** A small residual alone can coexist with a solution sensitive to small perturbations. A condition estimate adds information about that sensitivity, but does not validate the physical model or mesh.

GHOST generally estimates a 1-norm condition number using existing inverse/factor operations; it does not routinely compute a full SVD just for this diagnostic. BoR's LU route uses LAPACK `gecon`, which explicitly reuses LU factors. [LAPACK documentation](https://www.netlib.org/lapack/explore-html/d4/daf/group__gecon_ga58588d37cad394b43f211baa0a4684de.html).

| Measured 2D backend | Condition work as percentage of profiled solve time |
| --- | ---: |
| Dense | 0.8–1.9% |
| Compressed | 2.0–6.1% |

These figures use the instrumented condition-estimation and condition-scaling stages, rather than attributing noisy differences between separate short runs entirely to condition checks. They are not measurements of large BoR workloads.

Estimation is associated with a factor/system, not repeated independently for every look angle. Low-level 2D entries default condition calculation off; survey/certified workflows enable it, and exploratory workflows can omit it. Main BoR solve paths enable it for their modal systems.

Three improvements would make it more consistent:

1. **Unify estimator behavior.** Dense 2D and approximate dense BoR use a deterministic wrapper; compressed 2D and compressed BoR call SciPy's estimator directly. That leaves inconsistent handling of random probes. The current deterministic wrapper holds a global lock across estimation; replacing it with a shared implementation that owns its random state could also avoid serializing parallel approximate BoR estimates. Measure that contention before claiming a speedup.
2. **Report the actual method and scaling.** 2D uses an equilibrated estimate with additional policy handling; BoR uses an unscaled estimate. The thresholds are not directly comparable. BoR metadata currently labels non-compressed estimates `lapack_gecon_1norm` even when hierarchical or mirror factors use an inverse-operator estimator.
3. **Batch probes and time them consistently.** Preserve acceptance checks while removing avoidable per-column overhead. Explicitly distinguish skipped estimates from successful conditioning checks in results.

These estimates are diagnostics, not rigorous certificates of forward accuracy. In particular, SciPy documents `onenormest` as a lower-bound estimator for the operator norm; approximate inverse applications introduce further qualifications. [SciPy documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.onenormest.html).

## Recommended order

1. Correct backend-selection explanations and condition-method metadata; repair the stale test below; remove the small proven dead calculations/branches. Low numerical risk, primarily maintenance benefits.
2. Add representative large 2D and BoR workload timings, including assembly, conditions, accepted/rejected certification attempts, and fallback time. Use existing profiling rather than introducing extra calibration solves into normal runs.
3. Consolidate condition estimation and add bounded BoR block probes. Preserve current thresholds and compare failure behavior as well as fields.
4. Use those measurements to improve backend crossover and expensive adaptive retry decisions. Retain dense and compressed implementations.
5. Simplify the ordinary interface and explicitly deprecate unsupported legacy paths. Treat tolerance relaxation as a later numerical investigation, not housekeeping.

## Evidence and limits

Benchmark environment: Python 3.11.0, NumPy 2.4.2, SciPy 1.16.3, two assembly/BLAS threads; 0.6 GHz, 91 angles, both polarizations, fixed global P1 meshes, no mesh certification. Four fixtures × two backends × condition on/off × three trials = **48 successful baseline runs**. The separate refinement sensitivity experiment added **18 successful runs**. Warm-ups were excluded and configuration order alternated. These smooth, electrically small 2D fixtures isolate backend overhead; their panel counts do not make them representative electrically large targets. No GPU or large BoR speed claim is established here.

Focused regression suites: `test_bor_demand_driven_operators.py`, `test_bor_modal_preparation.py`, `test_bor_compute_reuse.py`, and `test_compressed_path.py`: **60 passed, 32 subtests passed, 1 failed**. The failure is `RetainedPreparationTests.test_automatic_cap_retry_reuses_context_and_solved_mode_fields`: its `initial_small` mock does not accept the current `surface_wave_bandwidth` keyword. It fails before exercising the intended retry assertion. Consequently, source inspection supports that reuse path, but this run does not freshly verify that particular assertion. No solver edits preceded the test run.

Reproduction scripts, full measurements, summaries, and JUnit output are in the local, ignored [audit artifact directory](../../audit_ghost_performance_20261024/): `benchmark.py`, `benchmark.json`, `summary.json`, `environment.json`, `refinement_probe.py`, `refinement_probe.json`, and `targeted_tests.xml`. The numerical recommendations above distinguish measured effects from source-level opportunities; this was not an exhaustive physics recertification.
