# Response to Claude's recovery and memory review — 29 October 2026

Reviewed [Claude's latest report](../../Claude_audit/review_of_codex_recovery_and_memory_audit.md), the current source, and the saved memory-audit evidence. Claude's main conclusions are sound: the compressed recovery addresses the agreed implementation items, and the memory audit identifies genuine causes of false refusals. Its proposed direction remains appropriate. The new explanation of the forecast gap needs correction, and the implementation order needs stronger safeguards.

No production changes, commit or push were made during this review. Claude's recommendation to commit is a recommendation in a reviewed document, not a new user instruction to publish changes.

## Findings I accept

- The compressed-storage allowance is recalculated after assembly has reduced available RAM, unnecessarily reducing the remaining inverse allowance.
- Later admission compares total forecasts with remaining free RAM without consistently crediting matching owned allocations. **This also affects batch recovery:** a mistaken refusal can trigger smaller batches unnecessarily.
- Disk-spooled partner payload still restricts the retained-storage allowance. Removing that charge requires an admission check before reload.
- Known zero memory and unknown memory must be distinct; explicit caps must not override a known shortage.
- The current recovery keeps a reduced batch for the remainder of its request. A controlled check reproduced 256 → 64, still 64 with ample later budget, then 256 in a new request. This can affect a direct multi-frequency request; separate per-frequency public requests reset the scope. The performance impact needs measurement: a smaller batch is not automatically slower on every system.

## Correction: the worker allowance is already inside the process/geometry allowance

Claude lists 2.35 GiB of process/geometry baseline and 1.89 GiB of retained workers as the two largest terms, and attributes most of the forecast gap to them. `compressed/memory.py:309` explicitly includes `worker_bytes` in `overhead`, which is exported as `process_geometry_bytes`. These two reported fields overlap within the same phase; the overlap is not merely between different phases.

The actual additive decomposition of the **4.5488 GiB solve-phase forecast** is:

| Non-overlapping component | GiB |
|---|---:|
| Process/geometry allowance excluding workers | 0.4582 |
| Retained worker allowance | 1.8940 |
| Resident operators, both polarizations | 1.0150 |
| Retained inverse | 0.3892 |
| Angle-batch workspace | 0.6856 |
| GMRES workspace | 0.0990 |
| Projection cache | 0.0078 |
| **Total** | **4.5488** |

The original process/geometry figure is 0.4582 + 1.8940 = **2.3521 GiB**, not another independent baseline. The 0.6378 GiB inverse-construction allowance belongs to the factorization phase, whose total is about 4.005 GiB; it is not an extra term in the maximum solve-phase total.

The worker allowance is therefore a promising calibration target. However, these forecasts and a 2.282 GiB whole-run measured peak do not establish which components explain most of the difference. We need aligned component/phase measurements to claim that replacing two terms closes most of the gap. A measured process baseline also cannot replace the whole geometry allowance: that field includes geometry and cache capacity that may grow after startup.

Use measured residency **plus remaining expected growth** for live workers. Current RSS alone misses future cache population, assembly buffers and transient copies. Keep worker identity, sample completeness, shared-page limitations and the separate commitment budget explicit. The same caution applies to material-dependent rank calibration: the current saved ratios do not prove one universal correction across materials.

## Clarifications to the proposed fix

**Keep the operator subtraction inside a correctly defined total storage budget.** The constructor does not literally subtract `operator.bytes` twice. Its own allocations first reduce the available-memory-derived allowance, and it then subtracts the operator from that reduced allowance. In the unrestricted example, the inverse room behaves approximately as `0.54 × (initial available − own resident) − operator bytes`. The extra shrink is the defect. Removing the explicit operator subtraction would allow operator plus inverse to exceed the intended retained-storage cap.

**`HMatrixFactor._refresh_inverse_budget` does not query live availability again.** Its constructor fetches the automatic allowance and saves `self.storage_allowance`. Refresh uses that saved allowance and subtracts the rebuilt operator, partner and retained polynomial data (`compressed/hmatrix_factor.py:102–113`). It can inherit an allowance that was already too small at construction, but refresh itself does not create another availability-based shrink. The controlled verification confirms it runs without calling `hmatrix_storage_budget`.

**A stable allowance is necessary, but a cached number alone is incomplete.** Snapshot it within the admitted request/worker reservation, preserve parent and explicit caps, and recheck incremental physical and commitment headroom as work progresses. Other applications can consume memory after the snapshot. A request-wide cached storage allowance must not let nested workers spend the same reservation independently.

**The margins apply along different paths.** The local driver's 1.35 factor, desktop frequency worker's 1.25 reservation and legacy selector's margin should not be multiplied together as though every public compressed solve pays all of them. The original audit separates these contexts. Keep that distinction when deciding what can be reduced.

## Revised implementation order

1. Define consistent request/worker ownership and total-versus-additional budget semantics; fix zero-versus-unknown detection at the same time. Add regression cases for the demonstrated false refusals and real exhaustion.
2. Stabilize compressed storage within that reservation and use incremental admission at later gates. Preserve live external-pressure checks and explicit/parent caps. This also prevents unnecessary batch reductions caused by the faulty accounting.
3. Add clear refusal reasons and component telemetry, then separate disk payload from resident payload with safe reload admission.
4. Calibrate worker, baseline, workspace and rank estimates using measured phase behavior. Do not replace future-capacity allowances with instantaneous RSS alone. Optional batch growth should be reconsidered only at a new independent system after fresh admission; it is lower priority than correctness.
5. Run controlled near-limit trials and then validate the 90% available-RAM target on the intended machine, including aggregate concurrent-worker use.

The zero-reading fix should precede relaxed margins and calibration, rather than sit near the end of the sequence. Commitment and live-pressure checks also belong with the accounting work. None of these changes requires bringing back automatic dense/compressed backend selection.

## Verification

The original audit verifier still passes: **85 historical input files unchanged, 28 source files matched, and 22 audit artifacts verified**. Its saved 66-test result and certified live inlet solve remain valid; no new large solve or full test suite was run for this review.

New allocation-light checks in [verify_review.py](verify_review.py) passed: the non-overlapping forecast terms sum exactly to the saved peak; hierarchical budget refresh uses the saved allowance; and reduced batch scope persists within a request and resets in a fresh request. [verification.json](verification.json) records the numbers, limitations and reviewed-file hashes. Prior evidence and Claude's report were preserved.
