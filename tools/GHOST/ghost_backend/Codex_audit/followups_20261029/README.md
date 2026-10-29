# Implemented follow-ups and 15 GHz capacity checks

This implements the concrete follow-ups in the [response to Claude's review](../response_to_claude_large_geometry_review.md), and records the requested **15 GHz / 32 GB maximum RAM** assessment for a **2D cross-section**. The starting implementation was published as `bb25908`. This package records the subsequent implementation, validation and audit evidence.

## Production changes

| Follow-up | Implementation |
| --- | --- |
| Learn from a successful stronger inverse | New [preconditioner_hints.py](../../compressed/preconditioner_hints.py) stores small accuracy/size records within the request context. It learns only after a hierarchical field inverse passes physical and exact sample-row checks. Later compatible factors can start at 1e-10 instead of building at 1e-8 and upgrading. |
| Scope and admit every hinted build | Geometry, material directory, units and frequency identify the scope; formulation and oracle/factor class identify the entry. Adaptive refinement tags do not change the physical identity. A changed frequency or geometry gets independent state, and there is no cross-run cache. At most 16 records are retained, without matrices. The prediction scales prior inverse bytes quadratically when size grows; payload allowance is twice that prediction and construction headroom is at least three times it or 64 MiB. These are conservative admission heuristics, not hard transient-allocation bounds. |
| Recover when a hint fails | A construction rejection drops the hint and uses the ordinary initial policy. A hinted inverse that fails refinement gets one ordinary-policy rebuild. The optional upgrade is disabled for that retry to avoid immediately repeating the failed choice. Cancellation propagates and temporary budgets are restored. |
| Label condition-probe upgrades | Constructor condition probes are explicitly labeled in upgrade evidence. The learned hint is not recorded until a subsequent field solve passes its checks. Maximum refinement telemetry includes refinements discarded by an upgrade restart. |
| Preserve paired fallback evidence | Native and multi-region tile pairs attach admission evidence to both operators with TE/TM labels and the rejection reason. The regional rank/error rejection now preserves its marked pair for the admitted shared tile traversal; a combined-storage rejection still retries hierarchical assembly one polarization at a time. Integration tests cover both routes. |
| Give worker traversal exclusive ownership | Acquisition, release and idle eviction share a lock. Production acquisition marks the pool busy before preparation. A competing traversal cannot replace the payload or resize that active pool. Preparation failure, cancellation and traversal failure release the lease and close failed workers. Existing process recovery remains. |
| Make small batches understandable | Resource adjustments report requested/effective angle-batch counts and a progress notice explaining extra passes and factor reuse. No unmeasured time penalty or hard floor is invented. Exhausted admission reports formulation names and the final attempted batch, retaining the original exception. |
| Carry batch admission through reference-mesh fallback | While testing notices, the reference-mesh retry was found to retain the old batch after selecting a newly admitted smaller batch. It now executes and reports the admitted batch. Final metadata uses the reference solve's actual batch, rather than the last rejected adaptive step's batch. |
| Make forecast scope/loss visible | Candidate unknown-count ranges are explicitly labeled initial candidates, not predicted final sizes. Compressed forecast evidence retains up to 32 distinct complex medium wavenumbers, with a truncation flag, and states that the rank model is not attenuation-calibrated. Admission allowances are not reduced. |
| Bound Windows publication recovery | Runtime snapshot publication retries Windows access/sharing errors at most four times, with 0.05/0.10/0.20-second waits. Existing destinations are checked on each attempt; other errors and final failures propagate. Failed staging and locks are cleaned up. This is resilience to transient errors, not a claim that antivirus caused the earlier test failures. |
| Fix the headless log encoding contract | The headless test launcher explicitly requests UTF-8 output from its driver and descendants, matching the decoding used by the test. It no longer depends on the audit harness to set that contract. |

No public factorization mode or accuracy-gate relaxation is added. Dense and compressed remain available. Native coefficient algorithms, conditioning thresholds and mesh-convergence acceptance limits retain their existing definitions.

## Matched speed result

The same 12 ft by 3 ft high-contrast homogeneous material-filled inlet was tested at 1 GHz, with four threads, 361 angles, both polarizations and full adaptive certification. It is a TYPE 3 body, not a coated PEC duct.

| Configuration | Certified solve | Peak process-tree RSS | Total inverse builds across candidate meshes |
| --- | ---: | ---: | ---: |
| Existing per-factor upgrade, learning disabled | 43.16 s | 1.518 GiB | 8 |
| Request-owned learned preference | 38.40 s | 1.487 GiB | 5 |

This single serial comparison is **11.0% faster**, with **31.6 MiB less sampled peak RSS**. Final TE/TM inverses each build once rather than twice. All 361 angles remain, both quality and mesh-convergence gates pass, and the maximum normalized field difference is **5.64e-16**. This is measured on one workload, not a promised general speedup. The new hinted path is additionally compared with dense fields across seven material/geometry families in regression tests.

Raw requests, metadata, results, fields and process-tree monitors are in `benchmarks/`. [measurements.json](measurements.json) and [summarize.py](summarize.py) provide the reproducible comparison.

## Requested 15 GHz / 32 GB assessment

Two full 15 GHz Automatic solves completed with an **8 GiB requested solve budget**, deliberately below the user's ceiling. Both used four threads, 361 angles, both polarizations and unchanged adaptive certification. An external trial guard would stop the isolated process tree at 10 GiB RSS/private commit or ten minutes.

| Synthetic 12 ft x 3 ft metal contour | Initial maximum candidate unknowns | Final unknowns | Final Automatic choice | Observed solve time | Peak process-tree RSS |
| --- | ---: | ---: | --- | ---: | ---: |
| Inlet: 4 ft-deep, 1 ft-wide notch | 4,362 | 14,295 | Dense | 103.43 s | 3.971 GiB |
| Narrow inlet: 6 ft-deep, 3 in-wide notch | 4,815 | 15,849 | Compressed | 113.06 s | 4.750 GiB |

The narrow case starts with dense candidates and switches to compressed after refinement. Both final results pass quality and mesh-convergence checks. These results support handling these **specific metal cross-sections at 15 GHz within 32 GB**, and show useful roles for both execution paths. They are capacity/accuracy trials, not a controlled dense-versus-compressed speed comparison. They do not certify an arbitrary inlet, a coated duct or a finite 3D object.

The measured machine exposes about **31.10 GiB total RAM**; roughly **15.77 GiB was available** at one check during this work. A 32 GB machine cannot necessarily assign all its RAM to one solve. Production admission still uses live available memory. No availability override was used for the completed solves.

Separate [24/32 GiB scenario forecasts](capacity_15ghz.json) use hypothetical availability **only for geometry/resource arithmetic**, never numerical allocation:

| Material-filled inlet at 15 GHz | Initial candidate unknowns | Dense forecast | Compressed forecast | Interpretation |
| --- | ---: | ---: | ---: | --- |
| Moderate dielectric, epsilon 4 - 0.04i and mu 1 | 17,424 | 8.68 GiB | 6.62 GiB | Initial candidates fit the scenario budgets; this is not a completed or final-refinement capacity result. |
| High-contrast lossy magnetic material from the audit | 194,124 | 935.84 GiB | 474.48 GiB | Current conservative admission refuses it at 32 GiB, even after batch reduction. No completed solve establishes that it fits. |

The high-contrast estimates are uncertain and conservative, but the new loss experiment does not justify dividing a 15 GHz prediction by an observed low-frequency ratio. Angle batching still cannot make an oversized operator or factor fit. The real geometry and material assignment are needed for a dependable case-specific assessment.

## Experimental follow-ups and decisions

### Controlled loss study

A fixed 12 ft x 3 ft inlet mesh, 1 GHz frequency, quadratic basis and 1e-10 inverse accuracy were held fixed while the imaginary parts of epsilon and mu were scaled. Real material parameters stayed fixed; the resulting complex wavenumber was recorded. Both polarizations were tested. These are algebraic calibration experiments with synthetic RHS columns, not mesh-converged physical-field certifications.

The first 512-panel mesh passed loss multipliers 0 and 0.25, but the highest-loss case was rejected by the existing near-quadrature convergence gate. Its failures are retained in [loss_study.json](loss_study.json). The entire experiment was repeated on one fixed 1,024-panel / 4,096-unknown mesh, without relaxing that gate:

| Loss multiplier | Forecast inverse rank | Measured inverse ranks TE / TM | Measured inverse bytes TE / TM |
| --- | ---: | --- | --- |
| 0 | 967 | 198 / 201 | 99.2 / 100.4 MB |
| 0.25 | 981 | 120 / 125 | 50.7 / 51.9 MB |
| 1 | 1,143 | 89 / 90 | 46.3 / 46.4 MB |

All six refined experiments passed operator/sample-row checks and an independently streamed full-row residual check; the largest normalized full-row backward error was 5.56e-15. See [loss_study_refined.json](loss_study_refined.json).

Loss clearly affects this system's ranks, while the magnitude-only forecast moves in the opposite direction. However, the lossless case is already substantially overpredicted. Loss is not the sole explanation for conservatism. More geometries, resolutions, frequencies and withheld validation cases are required before an attenuation-dependent admission formula is safe. The production change therefore preserves the medium data and clearly labels the model, while retaining its allowances.

### Near-field leaf experiment

Reducing the H-matrix leaf parameter from 128 to 64 in the fully certified 1 GHz inlet run reduced peak RSS from 1.487 to 1.290 GiB, saving **202.1 MiB**, but increased time from 38.40 to 46.69 seconds (**21.6% slower**). The same final mesh and quality gates passed; normalized field differences were at most 2.87e-10. This is a tradeoff, not a universal improvement, so the production default remains 128. The experimental override exists only in the audit runner.

### Reciprocal query prototype

A bounded 32 MiB whole-query cache was tested on the existing exactly symmetric scalar Helmholtz test kernel. It supports direct and transposed cache hits without assuming that a material transmission system is symmetric. Both cached/uncached solves matched an independent dense solve within 3.98e-14. But there were **zero hits** across 134 calls / 792,000 queried entries, despite storing about 18.4 MiB of payload and index data. See [reciprocal_query_study.json](reciprocal_query_study.json).

This rules out shipping that particular cache as a speed improvement for the tested query schedule. It does not rule out reuse of smaller primitive kernel blocks, coordinated adaptive queries, or formulation-specific reciprocity. That deeper redesign remains open. No unproductive cache was added to production.

## Validation and review package

**223 unique regression tests pass** using the latest saved result for each test, plus five certified end-to-end trials and six refined loss experiments. Repeated runs and unittest subtests are not counted as additional unique tests. [verification.json](verification.json) records the source, report-link and experiment checks.

[validation_summary.json](validation_summary.json) records the latest outcome for every unique test across this follow-up's runs. Timestamped reports preserve development failures and successful fixes. Coverage includes compatible/incompatible hint scopes; memory refusal, construction failure, solve failure and cancellation; seven material-family comparisons with dense fields; paired native/regional rank rejection; separate hierarchical retry after paired storage rejection; concurrent pool ownership and preparation failure; bounded publication retries, destination races, cleanup and integrity; batch notices and reference-mesh propagation; headless workers; original H-matrix numerical and capacity regressions; and the shared BoR compressed path.

The new integration checks exposed the regional paired-fallback behavior described above and verified its correction. One earlier test-only failure used a mock operator without its required length interface; that fixture was corrected. Neither failed attempt is hidden from the saved reports.

Review [implementation.patch](implementation.patch), [changed_files.json](changed_files.json), `before/`, and `after/`. [capture.py](capture.py) generates the diff, checks current source hashes and validates report links. [operator_experiments.py](operator_experiments.py) reproduces the research work; [capacity_probe.py](capacity_probe.py) reproduces certified trials, and [capacity_15ghz.py](capacity_15ghz.py) produces the explicitly hypothetical budget scenarios.

Active matrix/factor disk streaming, FMM, a smaller-preconditioner capacity backend and distributed single-matrix solves are not implemented by this follow-up. The changes improve the current solver's behavior without claiming those new architectures or an unlimited-size desktop solve.
