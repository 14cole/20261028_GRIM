# Review handoff: fixed-compressed memory recovery and diagnostic labeling

Implemented the agreed fixes from your compressed-default review and response. Start with `Codex_audit/compressed_recovery_20261029/README.md`, `validation_summary.json`, `implementation_hashes.json`, and `diagnostic_derivative_manifest.json`. The pending working-tree patch is still based on `5460aa2` and includes the preceding compressed-default change.

Review priorities:

1. Recovery at the actual monostatic admission boundary: release idle workers, reprice with live limits, reduce angle batches down to one, keep all angles and remain compressed. It must not retry arbitrary failures after assembly or factorization.
2. Request-local batch scope: nested channels/refined meshes must honor reductions; success, exceptions and cancellation must restore the outer state. Metadata must agree with the batches used by field execution.
3. Worker consistency: `_plan` carries `angle_batch_size`, `_compute` caps worker options to that value, and an unfit fixed backend is deferred even if another backend fits the forecast.
4. Diagnostic export normalization: all production certification flags must be false while diagnostic comparisons and numerical values remain available. Timing recording is suppressed during relaxed checks, before normalization, and rejects labeled diagnostic metadata afterward.
5. Preservation: the corrected coated diagnostic is a separate derivative; all 105 original evidence hashes still match. No production quality thresholds were relaxed. The old hashed numerical evidence is unchanged.

New tests are `tests/test_compressed_recovery.py` and `tests/test_diagnostic_exports.py`. The controlled refusal reproduction now succeeds at batch 64 with all 361 angles; a refined cubic mesh recovers at batch 16. Fresh-worker checks cover an already reduced plan and a worker whose actual reservation requires a further reduction. Oversized-at-one, cancellation, busy-pool, no-dense-retry, and normal-export cases are covered.

The broad integration run passed 233 tests and 37 subtests. Consult the saved summary for final additional checks. No new full-size capacity or timing trials were run. The fix improves admission behavior; it does not establish that all 12-foot, 15 GHz geometries fit 32 GB.

No commit or push was performed. Ordinary runs remain compressed by default, and saved explicit legacy Automatic profiles retain their compatibility path.
