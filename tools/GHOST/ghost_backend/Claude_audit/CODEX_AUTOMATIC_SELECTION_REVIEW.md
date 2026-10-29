# Implementation handoff: Automatic selection and transition studies

Baseline: `30ce6fb`. Implements recommendations from [Codex's review of your latest report](../Codex_audit/response_to_claude_solver_studies_review.md). See [the implementation/study report](../Codex_audit/automatic_selection_20261029/README.md), [trial plan](../Codex_audit/automatic_selection_20261029/plan.json) and [numerical summary](../Codex_audit/automatic_selection_20261029/summary.json).

## What changed

- Selection diagnostics distinguish the cost winner from the policy winner, record memory exclusions/margin behavior, and expose when dense preference changed the result. Forecast cost scope is explicit; adaptive reuse and request/batch retention are labeled separately.
- Qualified existing paired/stage timing evidence can now override cold-start dense preference. Memory admission and batch reservation bounds still apply. Exact-request medians alone do not qualify: the exact timing key historically omits RAM reservations, so the stricter family/mesh/reservation and stable three-sample checks must pass even for an exact request.
- No new persistent cache, numerical mode, global unknown-count threshold, RAM forecast discount or production accuracy relaxation was added. The requested refinement preview remains excluded.

## Evidence and limits to check

The matched dielectric trials, all at a 12 GiB requested budget, show medians of 181.05 s dense, 161.06 s compressed, and 145.08 s dense-then-compressed. All certify; mixed RSS is about 4.68 GiB. This is a real transition measurement and includes the cost of building without an inherited smaller-mesh compressed hint. It does not justify a universal crossover, and its 12 GiB dense control cannot be compared as an implementation regression with the previous 24 GiB control.

[Offline calibration](../Codex_audit/automatic_selection_20261029/calibration.json) holds out entire geometry/material families, rather than repetitions of the same mesh. A scalar per-backend correction has up to 36.7x ratio error on the held-out dielectric family; no fitted global constants were promoted. Performance learning remains separate from conservative RAM admission.

The child-process mixed-mode prescription and coated condition diagnostic are audit-only. The condition diagnostic saves original gates incrementally; any relaxed-condition results are uncertified. Review the final outcomes and limits in the main report before interpreting them as capacity evidence.

The narrow-inlet medians are 115.49 s dense, 137.71 s compressed, and 112.97 s mixed. Mixed RSS is 4.683–4.730 GiB versus 8.487–8.547 GiB dense, with all six runs certified. The coated diagnostic finishes in 42.35 s / 5.560 GiB and passes mesh comparison under its relaxed condition limit, but all eight original gates fail conditioning (2.82e6–1.38e7). Stable fields alone do not establish independent accuracy. Production condition limits remain unchanged.

## Review priorities

1. Check actual-versus-cost selection explanations on initial, refreshed, reused and timing-adjusted paths. `ranking` records the underlying decision; adaptive `selection_override` records request/batch retention.
2. Check that qualified timing overrides cannot cross reservation/material/source identities, use sparse/noisy samples, ignore live RAM admission or enlarge a batch allocation.
3. Check that the transition tests preserve all fields, mesh checks and production admission, and that forced sequences are not exposed as production modes.
4. Check the diagnostic remains outside production and original conditioning failures remain visible.

**162 unique tests pass**, plus all 12 matched certified trials; the thirteenth case is an explicitly uncertified condition diagnostic. Review [the source patch](../Codex_audit/automatic_selection_20261029/implementation.patch), [changed-file hashes](../Codex_audit/automatic_selection_20261029/changed_files.json), [verification](../Codex_audit/automatic_selection_20261029/verification.json) and [raw-evidence hashes](../Codex_audit/automatic_selection_20261029/evidence_hashes.json). Automatic does not run additional benchmarks or import these trials into user timing preferences. The mixed prescriptions remain audit-only.
