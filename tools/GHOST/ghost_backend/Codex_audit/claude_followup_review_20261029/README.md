# Review of Claude's impedance follow-up audit

Reviewed 2026-10-29 against `Claude_audit/review_of_codex_impedance_followups.md`, current source, and saved trial evidence.

## Verdict

Agree with keeping the implemented diagnostics and leaving the experimental memory pilot disabled. Compressed remains the default; dense remains an explicit user override. The dense estimate is guidance for a new attempt on the failed mesh, not a guarantee that the complete adaptive solve will fit or finish faster. Surface impedance also remains an explicit material approximation.

Claude's next-step proposal needs revision: construction memory is not fully checked before allocation, and stopping the later retries would not have saved 57 seconds in the recorded case. No production code or solver settings were changed during this review; nothing was pushed.

## Findings

### 1. Construction safeguards must precede forecast discounts

Claude correctly identified this prerequisite. Source inspection confirms it is not yet satisfied end to end:

- `compressed/factor.py:61` checks the factorization forecast before a fresh build. This is useful admission control, not a reservation around every temporary allocation.
- `compressed/inverse.py:155` caps counted retained storage. In `build`, both off-diagonal blocks are constructed before their storage is reserved at line 224. At line 232, the Woodbury correction matrix is allocated before `factor` checks its factor-storage allowance.
- `compressed/hmatrix_factor.py:85` constructs probes and invokes the sampled range finder. `linalg/hierarchical.py:288` bounds rank and sample width, but basis growth, projection, QR/SVD and output products have temporary arrays without a corresponding live-memory admission check around each operation.
- The normal compressed checkpoint delegates through `compressed/runtime.py:141` to the CPU/session checkpoint; the CPU implementation at `execution/cpu.py:101` checks cancellation and progress, not allocation headroom.

These paths have useful size limits and bounded product panels. They do not establish a complete live-allocation bound under a reduced forecast. This is an existing limitation, not a regression introduced by the diagnostic changes, and no out-of-memory failure was reproduced in this review.

Before discounting forecasts, account for the simultaneous construction live set: retained tree data, growing bases, projected matrices, QR/SVD/LU copies and workspaces, correction products, and any old/new preconditioner overlap. Check capacity before allocating and release failed-build references before retries. Tests should force rejection before large allocations, verify cleanup, and exercise changing headroom and concurrent requests.

### 2. The proposed 57-second saving is unsupported

The saved `full2_diagnostic/result.json` reports:

| Work | Seconds |
|---|---:|
| Entire failed request | 56.666 |
| Successful quadratic candidate | 54.500 |
| Cubic admission refusal | 0.242 |
| Conservative quadratic admission refusal | 0.404 |
| All work outside the successful candidate | 2.166 |

Stopping after the cubic memory refusal would still require the successful quadratic work and that cubic check. Thus even attributing all other work to avoidable overhead gives less than 2.17 seconds, not 57 seconds. The exact saving needs a controlled comparison. Leading with the closest refusal is a useful diagnostic improvement, but it should not be sold as a large speed gain.

A generic `MemoryError` also does not prove every larger candidate is impossible. The current handler covers forecast refusals, retained-storage rejection, and allocation failures. Different basis orders and execution paths have different storage/workspace costs; live headroom can change. Skip retries only when their actual resource requirements demonstrably cannot fit the applicable allowance. Preserve numerical and mesh-certification gates.

### 3. Same-request calibration is a study, not yet an admission rule

Measured quadratic storage can inform a cubic forecast without storing past solves. However, the measured/forecast ratio and a 1.5 margin are empirical: finer discretization can change ranks and required inverse accuracy. Retained inverse bytes also do not measure its construction peak. Leaving existing workspace terms unchanged does not prove those terms bound every temporary allocation.

Study this in shadow mode first: record proposed forecasts without changing admission, compare against measured construction peaks across independent materials, shapes and refinement steps, and include tight-memory failures. Existing request-local preconditioner hints already use measured inverse size for a different purpose; coordinate with them rather than introducing inconsistent accounting. An admitted cubic candidate would still need to solve and pass mesh certification before the 2 GHz case could be called successful.

### 4. Keep the pilot parked

Claude acknowledges that the proposed 0.6 cutoff was selected after seeing the data. It remains a hypothesis requiring independent validation. The held-out underestimate of 7.48% and lack of inverse-construction coverage still rule out production admission discounts. Sampling also has a runtime cost even if the resulting discount is not used.

## Suggested order

1. Keep the current diagnostic implementation.
2. Add construction-allocation accounting and pre-allocation checks, with focused failure/cleanup tests.
3. Gather same-request forecast calibration in shadow mode, including actual peak memory and inverse accuracy changes.
4. Consider forecast-aware retry skipping for clearer failures; expect a small saving in the recorded 2 GHz case.
5. Only after qualification, trial reduced forecasts on the full-size 2 GHz bulk case. Retain explicit dense and impedance overrides.

## Verification

All five implementation/test file hashes match the saved final implementation manifest. The earlier saved broad suite contains 158 passing tests and 39 passing subtests. This review additionally ran `test_failure_evidence.py`, `test_bounded_factor_workspaces.py`, and `test_hmatrix_resource_bounds.py`: **39 passed in 1.61 seconds**. These establish the behavior they test, not a complete construction-memory bound. No large numerical solves were rerun.

`verification.json` contains the hash comparisons and timing arithmetic. `validate.py` and `validation_results.json` retain the focused test command machinery and outcomes. Existing trial evidence was read without alteration.
