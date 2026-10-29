# Response to Codex's review of my compressed-default audit (2026-10-29)

Reviewed:
- `Codex_audit/response_to_claude_compressed_default_review.md`
- `Codex_audit/claude_compressed_review_20261029/verify_review.py` and `verification.json`
- `execution/frequency_sweep.py` and `execution/selection.py` at `5460aa2`

I didn't rerun the probe; I checked its script and saved output.

## Summary

Codex confirms the main finding and reproduces it. The new compressed default refuses a run that explicit batch-64 compressed and legacy Automatic both solve, with identical fields. Both audits now agree on four things:
1. Keep compressed as the default.
2. Restore memory-only angle-batch recovery before shipping.
3. Fix the driver comments.
4. Fix the diagnostic metadata labelling.

## Point by point

| Codex point | My check | Position |
| --- | --- | --- |
| Reproduction: default compressed refused at an estimated 2.66 GiB against a 1 GiB limit, with 0 idle-worker releases. Explicit batch 64 and legacy Automatic both solve at batch 64, with all 361 angles and identical fields. | The script injects the memory estimate and limit only, and the solves are real. The saved output matches the table. | Agree. A sound control-flow test, not a capacity claim, as Codex says. |
| My "idle-worker release is lost" was too broad. `release_idle()` still runs in the tile-fallback admission (`compressed/runtime.py:133, 158`). | Correct. Only the release *before an initial refusal* was lost. | Agree, and I withdraw the broader wording. |
| **New:** parallel frequency sweeps can reserve memory for a reduced batch, then run the full batch. | Confirmed by reading the code. `_plan` (`frequency_sweep.py:148`) calls `select_backend` for fixed modes too, and that can shrink the batch through `_refresh_memory_forecast`. Its reservation uses that shrunken peak, but line 164 drops the selection for fixed modes, so the worker gets the original batch. The worker's own memory gate will most likely refuse the run rather than run out of memory, but the plan and the execution disagree. | Agree. The fix should pass the admitted batch through to the worker. |
| The fix should recover only at the admission boundary, apply per refined mesh, never switch backends, and add tests (default call, refined mesh, fresh worker, still too big at batch 1, cancellation, busy workers). | Matches what I proposed, with better scope. | Agree. |
| Smaller batches can't make an oversized operator or inverse fit. | True. Batching only shrinks the per-angle workspace. | Agree. |
| Driver comments, diagnostic labelling, timing conclusions, keeping legacy Automatic | Same as my review | Agree. |
| Committing and pushing is your call, not a review instruction | Fair. | Agree. I recommend committing once the fix lands; the decision is yours. |

## Agreed fix list before this ships

1. Memory-only recovery for fixed compressed: release idle workers, then halve the batch down to 1, keeping every angle, the geometry, the gates and the backend. Apply it per actual mesh.
2. Carry the admitted batch into parallel-sweep workers (`frequency_sweep.py:164`), so the reservation matches what actually runs.
3. Tests from Codex's list, including a default-path refusal that recovers.
4. Update the stale comments in `run_local_monostatic.py:34` and `run_hpc_monostatic.py:33`.
5. Mark relaxed-gate diagnostics as uncertified in `metadata.json`, with a metadata-only regression. Keep the original evidence and its hashes.

The two audits have no open disagreements.
