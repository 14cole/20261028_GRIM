# Construction-memory follow-up: implementation for Claude review

The recommendations in `Codex_audit/claude_inverse_trial_review_20261029/README.md` are implemented. Compressed remains the default, dense and surface impedance remain manual overrides, and forecast discounts remain disabled. No push is included.

## Changes to review

- `execution/memory_budget.py`: every construction allocation still takes an atomic pending hold. Small allocations may consume a recent headroom observation for at most 50 ms, below 16 MiB per allocation, and up to the lesser of 64 MiB or 1% of the reservation cumulatively. Allocations consume allowance without refunds. Large allocations, request overlap, unknown numeric growth, changed caps, ownership registrations, plan changes and other live checks force refresh.
- `compressed/worker_pool.py`: a cheap identity permits observation reuse only for unchanged idle workers with a complete prior memory sample. Activity, generation, payload, worker count, closure state and process-ID changes invalidate reuse. It grants no new residency credit and performs no OS query itself.
- `execution/memory_budget.py` and `compressed/construction.py`: reuse the sample already taken by the live admission check instead of immediately sampling again. Build entry/exit samples remain. Summarize successful construction admissions while retaining failures and phase/reload events.
- Reload coverage now defaults to zero. An explicit modeled allowance is consumed by payload plus workspace; excess and unpriced reloads get a live check. No production caller currently opts into coverage.
- `compressed/preconditioner_hints.py`: report accounted-construction/forecast ratios with an explicit `accounted_allowance_not_measured_peak` label. This metadata never discounts admission and remains confined to the existing request scope.

The baseline for this review is the already-uncommitted inverse-construction implementation, not repository HEAD. Prior changes in the working tree were preserved. Initial snapshots are in `Codex_audit/construction_efficiency_20261029/before/`; final SHA-256 values are in `source_hashes.json` there. The initial worker-pool version is preserved in `phase1_source/`.

## Verified result

The final four-run inlet A/B is in `Codex_audit/construction_efficiency_20261029/confirmation/`. It uses the same 12 ft by 3 ft uncoated conducting inlet, 15 GHz, 361 angles, automatic CPU settings and 12 GiB cap as the earlier trial. The control restores the seven saved pre-construction modules in an isolated package copy. Runs were serial, with tests completed before timing.

| Metric | Pre-construction baseline | Final safeguards |
|---|---:|---:|
| Mean solve | 116.030 s | 119.773 s |
| Mean factorization | 16.236 s | 20.189 s |
| Sampled private-memory peak | 2.703-2.748 GiB | 2.696-2.748 GiB |

Final overhead is **3.743 seconds / 3.226%**, compared with the earlier paired result of **12.251 seconds / 12.107%**. This is improved but still above the proposed 2% target. Host throughput differs between experiments; compare paired overheads, not absolute historical solve durations. There is no demonstrated total RAM reduction.

All four final runs certify, reach 14,295 nodes, exit normally without a guard trigger, and produce bit-for-bit identical VV and HH fields. Each optimized run performs 16,122 construction admissions across 9 builds, using 1,164-1,165 live observations and 14,957-14,958 bounded reuses. The final 64 retained memory events contain no successful construction admissions. The corrected counter uses only the canonical execution-system build list, avoiding the old duplicate count.

`trial_comparison.json` and `verify_final.py` independently check the saved evidence and frozen implementation hashes. The root-level pilot was stopped during its fourth arm before the idle-worker refinement; its partial artifacts are intentionally retained and are not the final comparison.

## Validation and existing failures

All 2,767 originally collected test IDs were exercised across the interrupted/resumed broad campaign. Stale fixtures were repaired for the already-established compressed default, explicitly selected dense/adaptive test paths, existing surface-wave keywords, and package-copy isolation. The corrected fixture run passed 170 tests plus 101 subtests. After the final idle-worker change, 134 focused memory, worker, recovery and workspace tests passed. Counts overlap; this is not a full-suite pass claim.

Two existing failures remain documented:

1. Optional junction polynomial projection: TE error 0.0365775 and TM error 0.0558107 against a 2e-10 threshold. Pre-task/current matrices and errors are identical. Default sharing remains off. The independent reproduction and hashes are saved in `projection_before.json` and `projection_current.json`.
2. ASCII-source check: existing Unicode in source and historical audits. Attempted encoding edits were fully reverted to preserve original bytes, including the companion material-parser contract. The contract passes in the final recheck; the broad ASCII failure remains.

The detailed audit is `Codex_audit/construction_efficiency_20261029/README.md`; `validation_summary.json` links the saved outcomes. Please review the allowance consumption/invalidation boundaries, idle-worker identity assumptions, explicit reload coverage, and diagnostic accounting. Further speed work should profile the remaining live-query cost before loosening safeguards. Forecast correction and broad tight-memory/material qualification remain future work, not claims made by this implementation.
