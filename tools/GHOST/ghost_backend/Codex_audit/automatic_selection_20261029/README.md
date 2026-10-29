# Automatic selection implementation and follow-up experiments

Baseline: `30ce6fb`. Implements the recommendations in [the review of Claude's report](../response_to_claude_solver_studies_review.md). The user authorized representative materials/shapes, through 15 GHz with a 32 GB machine ceiling. The refinement-tripling preview remains excluded.

## Production changes

- Ranking now exposes the lowest-cost admitted candidate, the selected candidate, whether dense preference changed that winner, the memory margin used, and reasons for excluding other candidates. The explanation describes the actual decision rather than always claiming the lowest predicted cost won.
- Forecasts identify costs as an aggregate over their mesh systems and polynomial degrees. Refreshed forecasts replace stale ranking evidence. Reused adaptive forecasts preserve the underlying decision and label any request/batch preference separately.
- Costs derived from timing history identify their evidence source. The cold-start dense preference can now yield to the existing guarded paired-timing or stage-timing evidence. This does not create a new timing cache, retain solved matrices, add a mode, change RAM estimates, or relax numerical gates.
- Two exact-request timing medians alone cannot override the hierarchical dense preference: exact timing digests historically omit reservations. Even for exact matches, the override must pass the existing nearby-family checks, including reservation identity, actual mesh, at least three consecutive samples per backend, bounded spread, uncertainty and a winning margin. Nearby/stage evidence already has its own guarded matching rules. Memory admission and batch reservations are still applied after costing.
- Cold or insufficiently supported requests keep the existing preference. This is not a universal unknown-count crossover and does not automatically prescribe a mixed backend trajectory.

Automatic does not launch extra benchmark solves to obtain this evidence. It requires compatible paired records already accepted by the existing timing-history machinery. The audit trials use isolated empty histories and are not installed as user timing preferences. Consequently, this change does not promise the mixed-run timing for a new cold request.

`ranking` describes the underlying cost/policy decision. `selection_context` and `selection_override`, when present, describe how an adaptive step retains a request or batch preference. `cost_scope` remains the aggregate forecast scope even when a step reuses it. These fields are diagnostics; no new user-facing controls were added.

## Matched transition study

[The plan](plan.json) compares dense, compressed, and an audit-only prescribed transition on two 12 ft × 3 ft inlets at 15 GHz. Each mode has two repetitions in reversed order, all at a 12 GiB requested budget, four assembly/BLAS threads and 361 angles, with unchanged production quality and mesh checks. Each isolated process has an independent empty timing history, a 24 GiB process RSS/private ceiling, a 2 GiB host-headroom floor, and an eight-minute time guard.

For the moderate dielectric, the prescribed sequence is dense P2 then compressed P3. For the narrow metal inlet it uses dense for the first three meshes and compressed thereafter. The child-process experiment selects only from candidates admitted by the normal policy. It is not a production threshold or mode. Stage-event samples, final inverse hints/builds and optional dense-copy evidence are retained. Inclusive sampled stage peaks are not additive.

The source changes during this study concern selection evidence and qualified timing reuse. All study requests start without timing history, so the qualified-history override cannot affect them; the default ranking and numerical kernels are unchanged. The first dense worker predates the additional `cost_source` label. No timing model constants or admission forecasts were changed during the matched trials.

The dielectric repetitions are complete:

| 15 GHz moderate-dielectric inlet | Median seconds | Peak RSS range |
| --- | ---: | ---: |
| Dense | 181.05 | 5.817–5.852 GiB |
| Compressed | 161.06 | 3.987–3.989 GiB |
| Dense P2 then compressed P3 | 145.08 | 4.677–4.678 GiB |

The mixed sequence saves 19.9% versus dense and 9.9% versus compressed in these matched runs, while compressed alone uses the least RAM. The mixed final step has no inherited smaller-mesh H-inverse hint for its first polarization; its second polarization can learn from the first at the same final size. This confirms why adding independent step times had underestimated the transition cost. The largest normalized field difference from dense is 2.59e-8, and all six runs pass the unchanged gates and mesh certification.

These dense measurements use a **12 GiB budget**, unlike the earlier 24 GiB dielectric probe at 151.10 s / 9.96 GiB. Optional matrix copies can be declined under the smaller reservation. The difference is not a numerical-kernel regression and must not be presented as a before/after speed change caused by this implementation. No 16,000-unknown production crossover is inferred from these fixtures.

The narrow-inlet repetitions are also complete:

| 15 GHz narrow metal inlet | Median seconds | Peak RSS range |
| --- | ---: | ---: |
| Dense | 115.49 | 8.487–8.547 GiB |
| Compressed | 137.71 | 2.576–2.577 GiB |
| Dense first three meshes, then compressed | 112.97 | 4.683–4.730 GiB |

The mixed sequence saves about 2.2% in time versus dense and roughly 45% of peak RSS. Compressed alone remains the lowest-RAM choice. Normalized field difference from dense is at most 8.38e-13. All 12 matched trials certify. Ranges describe two repetitions, not confidence intervals or a universal speed guarantee. [The summary](summary.json) retains full timings, field comparisons, sampled stage peaks and final inverse/copy evidence.

## Offline calibration

[Calibration evidence](calibration.json) tests a simple seconds-per-work-unit correction separately for each backend, using ten unique mesh cases from three historical geometry/material families. Repetitions are collapsed before fitting. Each whole family is held out in turn, avoiding reuse of the same mesh's repetitions for training and validation. Initial P2/P3 costs are recomputed from individual mesh resources rather than treating an aggregate request forecast as a single-step prediction.

The baseline gets 3/4 ordinary-metal, 4/4 narrow-metal and 1/2 dielectric winner predictions right. The largest dense/compressed ratio error on the held-out dielectric family is **36.7x**. Budgets are recorded but this simple baseline does not model optional copies, hint history or operator reuse. This is negative evidence for deploying a universal scalar recalibration, not proof that a richer model cannot work. The existing `stage_work_v6` constants and conservative RAM allowances are therefore unchanged. The production improvement uses qualified local measurements instead of promoting this failed global fit.

## Coated-interface diagnostic

One isolated 3 GHz thin-coated inlet run records every original quality gate before temporarily relaxing only its condition limit in that child process. All original gate values and violations are flushed incrementally. The remaining checks and memory guards remain active. Any resulting fields are explicitly uncertified; a relaxed-gate mesh comparison does not establish physical accuracy or production capacity. This experiment is intended to distinguish a condition-gate stop from later accuracy, refinement or capacity failures.

The diagnostic completes in **42.35 s at 5.560 GiB peak RSS**. All eight original per-polarization gates fail solely on conditioning: estimates range from 2.82e6 to 1.38e7 versus the production limit of 1e6. Maximum residual is 1.31e-9. The adaptive sequence has 925 P2 panels, 925 P3 panels, then 1,491 and 2,447 P3 panels. The final comparison has maximum normalized complex-field changes of 3.90e-5 (VV) and 3.52e-6 (HH); regularized maximum dB changes are 0.00522 and 0.000283 dB. Thus the production condition limit blocks this example even though this particular relaxed-condition sequence produces stable fields.

This **does not certify physical accuracy**, show that the condition estimates are incorrect, or authorize loosening the gate. Errors common to both refined solutions can remain. Next work should compare equation scaling and condition estimation against an independent coated-inlet reference, retaining the original and scaled diagnostics. The saved gate snapshots predate some final metadata fields, so their polarization/degree labels are null; the final channel metadata and adaptive steps supply context. No causal claim about shell thinness alone is made.

## Reproduction

[study.py](study.py) is a separate audit runner derived from the previous bounded study; its source transformations apply only within individual experiment processes. [calibrate.py](calibrate.py) performs the held-out evaluation. [summarize.py](summarize.py) groups matched results without treating diagnostics as certified passes. [finish.py](finish.py) waits for numerical studies to end before running integration tests, avoiding benchmark contention.

The numerical runner was invoked with `--plan Codex_audit/automatic_selection_20261029/plan.json`; it refuses to overwrite existing case directories. All 13 planned cases have terminal evidence: **12 certified passes and one uncertified condition diagnostic**. The source patch is [implementation.patch](implementation.patch), with baseline/after hashes in [changed_files.json](changed_files.json). No production numerical kernels or quality/admission thresholds were modified.

## Validation and disposition

**162 unique tests pass.** The final integration set contains 108 tests covering selection evidence, automatic backends, paired/stage history, adaptive reuse, batch planning, execution-node selection and resource recovery. A further 54 tests cover large-geometry and earlier solver follow-ups. The initial 62-test run is retained but not added again to the unique count. [Verification](verification.json) confirms terminal case records, certifications and transition sequences, original diagnostic failures, passing test results, source hashes, audit syntax and report links. [Evidence hashes](evidence_hashes.json) cover 105 raw trial files.

The implemented policy change is supported by guarded local timing evidence, with explicit regression coverage for too few/noisy measurements, changed reservation families, unavailable RAM, batch limits and qualified stage evidence. The matched experiments establish potential gains for two particular switching sequences; they are not installed as a production size heuristic. The held-out calibration did not justify changing global cost constants. The coating diagnostic motivates independent conditioning/scaling work, not relaxing production checks.

Findings, implementation and reproduction material are ready for Claude's review in [the handoff](../../Claude_audit/CODEX_AUTOMATIC_SELECTION_REVIEW.md).
