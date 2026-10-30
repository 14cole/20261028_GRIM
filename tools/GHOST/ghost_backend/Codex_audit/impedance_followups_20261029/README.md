# Impedance audit follow-ups: implementation and bounded memory study

Implemented failure evidence and informational dense-override guidance. Compressed remains the default; neither numerical failures nor memory refusals trigger a dense solve or an impedance conversion. The memory pilot remains experimental because held-out measurements disproved treating its estimate as a storage bound.

## Production changes

- `execution/failure.py` preserves compact adaptive attempt records on the original exception, including completed/failed steps and rejection reasons. Exception type and cause remain intact. Python 3.11 traceback logs include one updated JSON diagnostic note; concise earlier reasons also appear in the ordinary error string.
- `twod/adaptivity.py` carries this evidence through the conservative retry, ineligible retry, numerical terminal failure and refused reference fallback. Cancellation does not trigger a new backend or diagnostic retry.
- `execution/cpu.py` adds same-mesh dense forecasts only to compressed numerical failures. The forecast uses the failed mesh, formulation, requested angle batch and current memory allowance, with the assumption that failed solve resources are released before a fresh retry. Temporary compressed batch shrink is reset for that estimate; environment-only launch settings are preserved. The message identifies the batch size, says fits/does not fit, and requires explicit selection. No dense matrix or factor is constructed.
- The estimate is not a whole-job promise: further refinement, live memory availability and convergence are checked again on an actual retry. Diagnostic estimation errors preserve the original numerical exception and record that an estimate was unavailable.

## What the reproduced failures now reveal

The full-size 2 GHz bulk request under the original 12 GiB study cap completed its quadratic candidate, then refused the cubic candidate at an estimated **13.28 GiB for 32,052 DOFs**. Its conservative retry was refused at **17.46 GiB for 42,708 DOFs**, followed by the linear fallback at **33.57 GiB for 85,462 DOFs**. These were admission failures, not evidence that mesh convergence itself failed. Previously only the last refusal survived.

The small refined magnetic case had compressed numerical failures at both adaptive coarsenings. The first failed cubic mesh received a roughly **3.64 GiB** dense estimate; the final, larger failed mesh received roughly **10.42 GiB** and was estimated to fit at that observation. No dense retry occurred. The historical 23.39-second dense run solved the original input through the smaller adaptive candidate; it was not a measured dense solve of the final doubled mesh. This corrects the overly broad earlier description of the two endpoints as the same final mesh.

A separate full-size 2 GHz trial requested a 16 GiB cap. Windows commit headroom still constrained admission: initial available physical memory was 16.27 GiB, initial available commit was 14.39 GiB, and the final effective allowance was about 12.15 GiB. The job remained refused. Raising a configured cap does not create OS backing capacity, and this study still has no measured full bulk solve at 2 GHz. OS/pagefile settings were not changed.

## Bounded operator pilot: evaluated, not enabled

The audit-only pilot samples actual hierarchical interaction lists using the real coefficient oracle for both polarizations. It is limited to eight lists, rank 64, four million queried entries, 262,144 entries per returned array and a 15-second cooperative time check. Each query checks 128 MiB of additional workspace against the existing request ledger. The external study watchdog also retains its process-tree and time bounds. This is an empirical sampling/work bound, not a proof of peak interpreter/BLAS memory. The script never changes the production model or admission plan.

Unobserved levels retain the original forecast. Predicted ranks use the fixed pre-study margin of 1.5 times the sampled maximum plus eight. Near-field storage remains exact in the model; inverse retention and construction estimates remain unchanged. Calibration uses the smaller magnetic case; the larger magnetic, moderate-dielectric and low-loss cases are held out. No margins were retuned to fit the held-out results.

| Case / DOFs | Geometry forecast GiB | Pilot GiB (target range) | Actual retained GiB (target range) | Pilot seconds |
|---|---:|---:|---:|---:|
| pilot_low_loss_control / 9,584 | 0.733 | 0.672-0.672 | 0.725-0.727 | 1.37 |
| pilot_low_loss_control / 14,376 | 1.269 | 1.176-1.178 | 1.177-1.181 | 1.34 |
| pilot_low_loss_control / 29,100 | 2.830 | 2.830-2.830 | 2.152-2.165 | 0.33 |
| pilot_magnetic_calibration / 12,036 | 0.908 | 0.538-0.538 | 0.384-0.384 | 1.05 |
| pilot_magnetic_holdout / 16,032 | 1.929 | 0.988-0.988 | 0.663-0.663 | 1.59 |
| pilot_magnetic_holdout / 24,048 | 3.098 | 2.910-2.910 | 0.836-0.836 | 1.01 |
| pilot_moderate_holdout / 9,584 | 0.733 | 0.671-0.671 | 0.719-0.721 | 1.38 |
| pilot_moderate_holdout / 14,376 | 1.269 | 1.174-1.176 | 1.165-1.169 | 1.28 |

The worst held-out operator underestimate was **7.48%**. The smaller magnetic forecast improved from about 0.91 to 0.54 GiB against 0.38 GiB actual, but that improvement did not transfer safely to every control. Limited coverage also left much of the larger-case overestimate intact.

All four pilot-study solves passed their unchanged numerical gates and mesh certification. The two magnetic runs produced fields identical to their saved pre-change references. Certification applies to the solves, not to the pilot memory estimate. Inverse construction can dominate the request: the refused linear fallback alone forecasts about 19.46 GiB of inverse-construction live set before the operator. Operator samples cannot justify discounting that cost.

**Decision:** do not enable this pilot as an admission discount. Further work would need better interaction coverage, independent inverse/construction evidence and tests near tight reservations. Existing live memory checks remain unchanged. No persistent history of past solves was added.

## Recorded trials

| Trial | Outcome | Elapsed solve/failure seconds | Peak tree RSS GiB | Peak private GiB |
|---|---|---:|---:|---:|
| full2_capacity_16gib | refused | 56.65 | 2.62 | 3.41 |
| full2_diagnostic | refused | 56.67 | 2.64 | 3.37 |
| pilot_low_loss_control | passed | 303.75 | 6.84 | 7.65 |
| pilot_magnetic_calibration | passed | 80.49 | 1.40 | 2.31 |
| pilot_magnetic_holdout | passed | 107.28 | 3.03 | 3.91 |
| pilot_moderate_holdout | passed | 102.90 | 3.52 | 4.38 |
| s50_refined_diagnostic | failed | 148.83 | 2.11 | 2.98 |

Windows private bytes are committed private memory; tree RSS is resident memory and can double-count shared pages. Peaks are sampled every 0.25 seconds. Trial times include experimental pilot work where enabled and are not a new production speed benchmark. Pilot trials followed the diagnostic reproducers serially. Regression tests ran after the numerical trials. The initial diagnostic reproducers precede final message-shortening and fresh-batch wording refinements; the final regression results cover the finalized implementation.

## Verification and reproduction

`tests/test_failure_evidence.py` checks exception identity/cause, structured evidence, traceback/pickle survival, ineligible and numerical retries, dense fit/non-fit estimates, unchanged memory plans, forecast failure, cancellation/input failures, no automatic dense allocation, fresh-batch pricing and environment-only settings. The existing CPU concurrency test now reserves one GiB for each simultaneous job and synchronizes their start, preserving numerical and state-isolation assertions rather than racing to claim all RAM.

Final test totals and command are in validation_summary.json. Raw validation attempts are retained; an early new-test mock-import leak and an existing unreserved-concurrency test were corrected before the final pass. Numerical evidence is in runs/, pilot predictions in pilot.json per trial, and aggregation in summary.json. `integrity.json` records unchanged historical evidence. The convenience impedance GUI was conditional in the review and was not added; the existing explicit IBC input remains available.

Reproduce the study in a fresh dated directory with `study.py --plan plan.json`, then `--plan capacity_plan.json`; existing run directories intentionally refuse overwrite. `pilot.py` is imported only by these audit workers. `analyze.py` rebuilds the comparison. The production failure helper is automatically included in backend source inventories and HPC runtime snapshots.
