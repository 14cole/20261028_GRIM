# Compressed memory recovery and diagnostic export fixes

Date: 2026-10-29. Implements the recommendations in `Claude_audit/review_of_codex_compressed_default.md`, `Codex_audit/response_to_claude_compressed_default_review.md`, and Claude's subsequent agreement in `Claude_audit/response_to_codex_compressed_default_review.md`. These changes extend the uncommitted compressed-default patch on `5460aa2`.

## Result

Compressed remains the default and dense remains an explicit override. A compressed system that exceeds its memory budget now releases idle tile workers, recalculates its forecast against live available memory, and reduces the angle batch until it fits or reaches one. It retains every requested angle. It does not restore the backend picker, read timing history for ordinary runs, change geometry/accuracy gates, or retry an arbitrary numerical/allocation failure after factorization.

Recovery runs at the monostatic memory-admission boundary immediately before assembly, using the actual mesh, polarization, resource counts and worker reservation. Later refined meshes are checked again. The reduced limit is request-local and restored on success, failure or cancellation. Explicit dense execution does not opt into this recovery policy.

Both planning and field execution use the same effective batch limit. Metadata records requested and effective limits, release allowance, each attempt's peak and budget, and whether admission succeeded. Adaptive steps and CPU execution reports include the effective batch. A failure at batch one reports that current batch rather than silently changing the backend.

Parallel frequency plans now carry the admitted batch into the worker's options. A forecast that admits only another backend is deferred to the parent instead of assigning an incompatible fixed-mode plan. The parent can then try the fixed compressed solve with its own reservation after workers have drained. This avoids reserving memory for batch 64 and accidentally executing batch 256.

## Diagnostic exports

The offline study worker now marks relaxed-check metadata as diagnostic and uncertified before saving it. This applies to root, per-channel, per-frequency, quality-gate and mesh-comparison certification flags. Original outcomes are retained under explicitly `diagnostic_...` keys; measured fields and numerical comparison values remain intact. Normal exports retain their existing passed/failed semantics.

A diagnostic scope prevents timing-history writes while checks are relaxed, including before export normalization. Already labeled diagnostic metadata is also rejected by timing ingestion, including nested diagnostic channel records.

The previous raw coated-diagnostic files were not rewritten. Use [the corrected metadata derivative](coated_diagnostic_metadata.corrected.json) for metadata-only consumption. Its provenance identifies the original metadata and original gate records by path and SHA-256. [The derivative manifest](diagnostic_derivative_manifest.json) verifies all **105 original evidence files** from that study remain byte-for-byte unchanged. The original audit's historical verification/implementation snapshots remain historical records; this follow-up has separate validation evidence.

Both monostatic driver comments now describe compressed as the default and dense as the manual override.

## Validation and limits

New tests demonstrate:

- A default compressed request under an injected 1 GiB admission limit reduces 256 → 128 → 64, solves all 361 angles in both polarizations, and matches the same explicitly batched numerical solution.
- A certified quadratic/cubic mesh pair rechecks memory and reduces further from 64 to 16 on the cubic mesh, with matching fields and certification preserved.
- Fresh Python workers execute an admitted batch 64 directly, or recover from 256 under their own 1 GiB reservation despite a 4 GiB request cap.
- An oversized operator still fails at batch one; cancellation restores request state; busy workers are never closed; idle workers can be released without reducing the batch when that alone is sufficient.
- Backend selection, dense retry and timing-history reads are not used by the fixed-compressed recovery path.
- The real audit worker's export path writes corrected diagnostic labels, leaves normal exports unchanged, and excludes diagnostic timings before export. Recursive metadata checks preserve diagnostic results and do not mutate the input.

The broad integration run passed **233 tests and 37 subtests**. Final targeted checks, including the final refusal message and unaffected BoR settings, are listed in [validation_summary.json](validation_summary.json). Test reports include one interrupted run caused by a test double being imported before its patch was restored; the test target was corrected and the integration suite rerun in a clean interpreter. This was a test-isolation issue, not a production failure.

These are small numerical regression tests with controlled memory forecasts, not new 12-foot/15 GHz capacity benchmarks. Smaller batches reduce angle-dependent temporary storage; they cannot guarantee an oversized operator or inverse will fit within 32 GB. Existing matrix compression, storage limits and numerical gates remain authoritative.

## Changed components

- `execution/angle_batch.py`: request-local recovery state and bounded admission retries.
- `execution/cpu.py`, `execution/options.py`: effective batch resolution, scope lifetime and execution metadata.
- `twod/solver.py`, `twod/adaptivity.py`: admission on actual meshes and accurate adaptive-step metadata.
- `execution/frequency_sweep.py`: planned batch propagation and fixed-mode admission checks.
- `execution/diagnostics.py`, `execution/timing_history.py`: diagnostic export labeling and history exclusion.
- `Codex_audit/automatic_selection_20261029/study.py`: corrected future diagnostic exports.
- `run_local_monostatic.py`, `run_hpc_monostatic.py`: corrected default-policy comments.
- `tests/test_compressed_recovery.py`, `tests/test_diagnostic_exports.py`: new regression coverage.

The implementation remains local and uncommitted. This task does not publish changes to GitHub. The earlier compressed-default files are still part of the same pending working-tree patch.
