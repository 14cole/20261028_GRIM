# Review of Claude's latest follow-up audit

Reviewed [Claude's audit](../Claude_audit/review_of_codex_followups.md) against implementation commit `4b0bfba`, the saved trial evidence, and three new instrumented two-frequency checks. This is a review; production code and admission policies were not changed. The earlier 223-test result is the saved implementation qualification, not a new full-suite run.

Claude's overall acceptance of the implementation is consistent with the evidence. I found no new blocking correctness defect in the paths reviewed. However, several proposed follow-ups depend on incorrect code readings or stronger conclusions than the experiments support. They should not all be implemented as written.

## Findings that change the recommendations

### 1. Direct multi-frequency calls already get independent enabled hint scopes

The claim that scripts or HPC calls to `solve_monostatic_rcs_2d` get no hints for a multi-frequency request is incorrect. In [solver.py](../twod/solver.py), `_frequency_local_co_solve` calls the decorated public entry separately with `[frequency]`. Both `solve_monostatic_rcs_2d` and `solve_monostatic_rcs_2d_certified` take this path before their single-frequency work. The nested [configured execution wrapper](../execution/options.py) then enters a fresh enabled single-frequency scope. The disabled outer sweep scope does not disable those inner scopes.

New actual numerical probes exercised a two-frequency direct call, global certification, and a certified call requesting adaptive meshing. All three passed, used hints within their compatible inner scopes, separated the two frequencies, and left no hint state after return. The probe forces the initial inverse tolerance to 1e-10 to make learning observable on a small fixture; it does not measure normal-case speed or relax acceptance gates. Global/reference certification may change the physical geometry snapshot and create additional compatible-scope boundaries; this is distinct from disabling hints for an entire sweep.

**Recommendation:** Do not add a second frequency-scope mechanism to these public entry points. Preserve the existing isolation and add this public-entry coverage to the regular regression suite if desired. Lower-level single-polarization helpers would need their own assessment if exposing them as supported production APIs.

### 2. Adaptive step timings already exist, and quantify the proposed saving

[adaptivity.py](../twod/adaptivity.py) already records `adaptive_mesh.steps[].seconds`. The raw `metadata.json` files contain them; the compact comparison summary omitted that field. Claude's statements that the benchmark files lack per-step timings and that this instrumentation remains to be implemented are incorrect.

| Trial | P2 initial | P3 initial | First spatial refinement | Final spatial refinement | First two / total solve |
| --- | ---: | ---: | ---: | ---: | ---: |
| Metal inlet, 15 GHz | 4.35 s | 5.27 s | 19.21 s | 74.24 s | 9.62 / 103.43 s (9.3%) |
| Narrow inlet, 15 GHz | 5.10 s | 6.37 s | 26.25 s | 74.98 s | 11.48 / 113.06 s (10.1%) |

These times include selection and any backend retries within each adaptive step. The early steps supply convergence comparisons and refinement indicators; simply deleting them would not preserve the algorithm. Their combined time is a ceiling on the saving from eliminating just those two steps while keeping later work unchanged, not a measured speedup from starting finer. A new initial P2/P3 pair could cost more and change the subsequent mesh.

**Recommendation:** Expose existing timings in the audit summary or UI first. Benchmark an alternative starting policy with unchanged certification before making high frequency alone trigger a finer start. Electrical size, material wavelengths and geometry matter in addition to GHz.

### 3. The loss-cap proposal is not demonstrated conservative

Claude recommends replacing magnitude-based wavenumber with a real-part/lossless value or capping it at the lossless forecast, asserting this needs no calibration. The six loss experiments do not establish that safety property across supported geometries, materials, frequencies, mesh sizes and inverse tolerances. Such a change would lower the operator/inverse forecast that feeds memory admission. A model overestimating six systems is not a bound for other systems, and matrix-factor construction can fail for memory independently of field-accuracy gates.

“Real part of the lossy wavenumber” also differs from “wavenumber after removing material loss” in these very data: the fully lossy interior wavenumber is approximately `420.85 - 204.63i`, while the zero-loss experiment is `391.60 + 0i`. Neither proposed substitution was tested as a general admission rule.

**Recommendation:** Keep current admission allowances until calibration includes weak-loss, lossless, multi-region, high-frequency and withheld cases. A clearly labeled experimental alternative can be compared offline. Do not describe it as already conservative or a proven capacity gain.

### 4. The proposed pilot-to-inverse mapping misreads the experiment

The quoted operator ranks 139/143 and 40 come from the completed operator's `evidence['max_rank']`, not from an isolated pilot-only forecast; see [operator_experiments.py](followups_20261029/operator_experiments.py). The measured inverse/operator maximum-rank ratios are:

| Loss multiplier | TE | TM |
| --- | ---: | ---: |
| 0 | 1.424 | 1.406 |
| 0.25 | 3.000 | 3.125 |
| 1 | 2.225 | 2.250 |

Thus the stated “1.4x to 2.2x in every loss case” is false. Maximum-rank ratios also do not determine total inverse bytes: ranks across the tree, dense near blocks and construction workspace contribute separately.

**Recommendation:** Collect pilot-only observations and full inverse storage separately before offering a calibrated “expected RAM” number. An experimental estimate could be shown with explicit uncertainty, but this dataset does not validate the proposed mapping. Keep it outside admission.

### 5. The dielectric capacity concern is valid; the predicted outcome remains unknown

The metal contours grew by 3.277x and 3.292x from the initial cubic mesh. This supports a labeled **“if refinement triples the unknowns”** planning scenario. It does not establish that a material-filled inlet probably follows the same growth or that compressed is “borderline” at 32 GB. Material-dependent discretization and convergence must be measured on that system.

There is also an inconsistency in Claude's growth table: the 1 GHz high-contrast trial stayed at **2,162 panels** and passed its initial P2/P3 comparison. The change from 8,648 to 12,972 unknowns is the planned polynomial-degree change, not spatial refinement beyond the largest initial cubic candidate. Its final/initial-cubic ratio is **1.0x**, not 1.5x. It does not support the statement that all three trials grew beyond their initial candidate meshes.

For the moderate dielectric, a hypothetical exact 3x increase from 17,424 gives **52,272 unknowns**. A single full complex128 square matrix would occupy **40.72 GiB**, before factor/workspace overhead. That conditional scenario clearly exceeds 32 GB for a conventional full dense representation. It is not an actual refined-mesh forecast; compressed storage cannot be inferred from this square-matrix calculation. Multiplying the entire original peak by nine is also not an exact repricing because the peak includes fixed, linear and quadratic components.

**Recommendation:** Add a scenario line, clearly separated from predicted initial admission and actual final certification. Reprice a representative refined mesh for backend-specific estimates if implementing it; do not relabel a scenario as an expected outcome. The completed 15 GHz metal trials remain valid for those particular 2D contours. The moderate dielectric has no completed 15 GHz capacity result.

## Smaller corrections and qualifications

- **The 11% speed result is one measured pair.** The earlier 44.60 s control and this round's 43.16 s control differ by about 3%, but two controls do not establish a noise distribution or an 8–14% interval for the improvement. Repeated, alternating matched runs would support a useful range. Retain “11% in this matched trial.”
- **Polarization sharing is real.** The hint key contains factor class, oracle class, formulation and kind, but not polarization. A compatible TM factor can use a TE byte reference. Its safety does not depend on a universal 3% size similarity: the hinted build has an enforced payload budget, a live-headroom check, rejection recovery and unchanged solve checks. Document the sharing; investigate separate polarization statistics if measured refusals or wasted builds justify them.
- **The 3x-size example requires two distinct checks.** For reference inverse size B and a 3x unknown count, the prediction is 9B, payload allowance 18B, and construction headroom `max(64 MiB, 27B)`. Claude's 18B description applies to payload, not the separate live-headroom requirement. Refusing a hint restores the ordinary build policy; it does not itself refuse the solve. These conservative factors remain heuristics, not proven transient-allocation bounds.
- **Predicted-versus-actual hint telemetry is already recorded.** `preconditioner_hint` includes reference bytes/size, predicted bytes, payload/construction allowances, available bytes and accepted actual inverse bytes. Broader analysis is needed; new basic logging is not.
- **“Any failure gets one rebuild” is too broad.** The optional policy handles the expected construction exceptions and refinement/GMRES rejections; cancellation propagates. Later physical-error and exact sample-row gates retain their own rejection/rebuild semantics. The accepted design does not promise recovery from every arbitrary exception.

## Recommended next work

1. Add an explicitly hypothetical refinement scenario to the preview, and show already-recorded step timings where useful.
2. Integrate the direct multi-frequency scope probes into ordinary regression coverage; no new frequency-scoping implementation is needed for the reviewed public paths.
3. Run repeated matched benchmarks before changing the initial mesh policy or quoting a typical percentage saving.
4. Extend rank/storage calibration before reducing admission estimates or claiming a pilot-based expected-memory model.

The current evidence still supports keeping dense and compressed behind Automatic selection. Claude's review supplies no new head-to-head result showing that either can be removed. Out-of-core active factorization, FMM and distributed single-matrix execution remain separate architectural work.

The [verification script](claude_followup_review_20261029/verify_review.py) and [machine-readable evidence](claude_followup_review_20261029/verification.json) reproduce the new probes and extract the timing/rank arithmetic. The evidence records an initial probe assertion correction: global certification can legitimately create more than two identities when its physical snapshot changes. No solver failure or failed accuracy gate occurred in those probes.
