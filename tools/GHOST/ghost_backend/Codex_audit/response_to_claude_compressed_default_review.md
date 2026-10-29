# Review of Claude's compressed-default audit

Date: 2026-10-29. Reviewed `Claude_audit/review_of_codex_compressed_default.md` against the current working tree on `5460aa2`. The implementation is still uncommitted locally. This review does not independently query GitHub's current branch, change production code, commit, or push.

**Claude's main finding is correct: keep compressed as the default, but restore automatic memory recovery within compressed before shipping this change.** Backend choice and angle batching are separate decisions. Removing automatic dense/compressed selection should not remove the ability to solve the same angles in smaller batches.

## Confirmed regression: missing automatic batch recovery

`execution/options.py:602` enters the request selector only for the legacy `adaptive` backend. `twod/adaptivity.py:168` likewise gates mesh-level reselection on `automatic_backend_requested()`. The recovery in `execution/selection.py:169` therefore no longer runs for ordinary sequential compressed requests. The monostatic admission gate at `twod/solver.py:2484` raises immediately if the forecast exceeds the budget.

I reproduced the gap using a real small rectangle solve with 361 angles, while injecting a deterministic memory forecast and a 1 GiB admission limit. Dense was deliberately forecast above that limit, so the successful legacy request also had to remain compressed. The synthetic forecast is 2.66 GiB at batch 256, 1.38 GiB at batch 128, and 0.74 GiB at batch 64. Actual matrices were small; this is a control-flow regression check, not a large-geometry capacity measurement.

| Request | Result | Effective batch | Idle-worker release calls | Returned angles per polarization |
| --- | --- | ---: | ---: | ---: |
| New default compressed | Memory refusal | 256 requested | 0 | None |
| Explicit compressed with batch 64 | Solved | 64 | 0 | 361 |
| Explicit legacy Automatic | Solved using compressed | 64 | 1 | 361 |

The successful requests returned matching complex fields for both polarizations, checked at relative tolerance 1e-10 and absolute tolerance 1e-12. Legacy Automatic reported the reduction from 256 to 64 and retained every requested angle. Reproduction and exact output: [verify_review.py](claude_compressed_review_20261029/verify_review.py) and [verification.json](claude_compressed_review_20261029/verification.json).

The previous 138-test validation did not cover this behavior. Its checks establish that the fixed backend does not change and that numerical results remain correct on admitted cases; they do not establish that all recoverable memory refusals are handled. My earlier statement that batching was retained was incomplete: fixed batching remains, but automatic batch reduction was lost from the normal sequential path.

## Scope corrections and implementation requirements

Claude's idle-worker statement is too broad if read as saying all cleanup disappeared. `compressed/runtime.py:133` and `:158` still call `release_idle()` when admitting a hierarchical-to-tile fallback. What disappeared from the default path is the earlier forecast-level cleanup/repricing and batch-reduction opportunity. That surviving fallback does not repair an initial admission refusal because the solve stops before reaching it.

The eventual fix should:

1. Admit the chosen compressed backend independently of backend ranking. On an admission failure, release only idle workers, re-evaluate the live budget, and reduce the angle batch down to one if useful. Preserve every requested angle, the geometry, and accuracy thresholds.
2. Apply this on the actual mesh for each relevant polarization/refinement step, rather than assuming an initial coarse forecast covers later refinement. Respect the current worker reservation and memory already retained by the solve.
3. Ensure effective batch sizes reach worker execution and metadata. In `execution/frequency_sweep.py:164`, fixed modes discard the selection record, while workers enter the unchanged payload options. That path must not reserve memory using a reduced batch and then execute a larger one. This is a code-inspection follow-up, not a separately reproduced parallel failure.
4. Recover at a well-defined admission boundary. Do not blindly retry arbitrary allocation or numerical errors after partial factorization. Compressed must remain selected throughout; do not restore timing history or the backend chooser.
5. Test recovery through an ordinary default call, refined meshes and a fresh worker. Also cover a case that remains too large at batch one, cancellation, busy-worker protection, complete angle output, and numerical agreement with the same manually reduced batch.

Smaller batches reduce temporary angle-dependent workspaces. They cannot make an irreducibly oversized operator/inverse fit. This fix would improve memory-constrained usability; it would not prove that every complex 12-foot, 15 GHz geometry fits within 32 GB.

## Other review items

| Claude finding | Verification / disposition |
| --- | --- |
| Stale driver comments | Confirmed at `run_local_monostatic.py:34` and `run_hpc_monostatic.py:33`. They still describe automatic backend selection immediately after the new compressed default. Update alongside the recovery fix. |
| Coated diagnostic certification flags | Confirmed again by reading the saved files. `result.json` says diagnostic/uncertified, but `metadata.json` still reports a passed quality gate and mesh certification. This is an audit-export labeling defect, not evidence that production gates were changed. Correct future exports and publish a labeled corrected derivative of the existing hashed evidence. Preserve the raw artifact and original hashes. |
| Not committed/pushed | Local uncommitted state confirmed. Publication status is a workflow fact, not a numerical defect. Claude's recommendation to push is not an instruction from the user to publish during this review. |
| Timing conclusions | Consistent with the previous reproducible comparison: no demonstrated five-minute single-solve dense saving in the examined pairs. No new timing benchmark was run here. The compressed-default decision remains justified. |
| Keep legacy Automatic for saved profiles | Agreed. This review does not recommend resuming its speed-model tuning. |

## Recommended sequence

First restore memory-only batch recovery and test the normal default/worker paths. Fix the two driver comments in that patch. Correct diagnostic export labeling with a metadata-only regression and preserve the prior evidence. Then the implementation can be reviewed for publication. Longer-term effort should stay on compressed memory scaling and independently checked coated/concave-geometry accuracy, rather than another dense/compressed picker.

No production fixes were made as part of this review. The regression and audit-labeling issue remain open.
