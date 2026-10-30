# Review of Claude's construction report and inlet trial

Read on 2026-10-29: `Claude_audit/inverse_construction_report_20261030.md`, `review_of_codex_inverse_construction.md`, and the completed `inverse_checks_ab/` experiment, including its script, results, metadata, monitor records and field arrays. This review changes no production code and launches no new solves.

## Main result

The end-to-end trial supports keeping the construction safeguards but optimizing their overhead. The report's opening statement that the trial has not run is stale: four successful, certified runs were saved afterward.

| Metric | Baseline | Current checks |
|---|---:|---:|
| First solve | 101.353 s | 113.388 s |
| Second solve | 101.026 s | 113.492 s |
| Mean solve | 101.189 s | 113.440 s |
| Mean factorization | 15.600 s | 27.777 s |
| Sampled peak tree private memory, range | 2.656–2.687 GiB | 2.656–2.705 GiB |

The total increase is **12.251 seconds, or 12.107%**. Factorization accounts for 12.177 seconds of that increase. Assembly and linear-solve times are close across arms. This is stronger evidence than the earlier small inverse benchmarks, though it is still only one geometry with two repetitions per arm. The A/B compares the entire construction implementation, not separately timed individual OS calls.

All four VV and HH field arrays are bit-for-bit identical, verified directly from `fields.npz`. All runs passed quality and mesh-convergence certification, reached the same final 14,295-node mesh, exited normally, and triggered no monitor guard. The sampled peaks provide no meaningful evidence of a whole-solve memory reduction.

The supplied geometry spans 144 by 36 inches: **12 feet by 3 feet**, at **15 GHz**, with a concave inlet notch, 361 angles, an uncoated conducting boundary, and no dielectric regions. It used automatic CPU settings (initially 8 assembly workers and a 2-thread BLAS reservation) under a 12 GiB solve cap. This is a successful representative case at the user's requested size and frequency. It does not establish that the materially harder bulk magnetic, coated, or arbitrary complex-geometry cases will also fit.

## Correct the reported check count

`ab.py::collect_construction` recursively collects duplicate copies of diagnostics: channel summaries, top-level factors, shadow observations and execution-system records all repeat some builds. Its reported **58,482 checks across 21 records** is therefore inflated.

Counting only `experimental_cpu.systems[*].preconditioners[*].construction`, each current run has **9 actual recorded builds and 16,122 construction checks**. The request ledger reports 16,500 total memory checks, consistent with that count plus other checks. The timing measurements do not depend on this mistake and remain valid. Identical record contents should not simply be deduplicated globally, because distinct builds can legitimately have identical statistics.

## Assessment of Claude's recommendations

1. **Optimize live queries: agree, with a constraint.** The 12.1% measured overhead exceeds Claude's proposed 2% threshold. Preserve per-allocation ownership, retained caps, pending holds and atomic admission. If OS samples are reused, do it through a bounded headroom allowance with explicit consumption, invalidation and refresh rules, including peer activity and elapsed time. A generic small-allocation exemption could reopen the cumulative-allocation problem. Removing redundant process/worker sampling is a useful first target. The suggested 16–32 MiB / 64 MiB / 1% thresholds are hypotheses, not qualified settings.

2. **Preserve useful diagnostics: agree, and confirmed in the trial.** In each current run, 58 of the final 64 retained memory events are construction admissions. Summarize successful construction checks separately while retaining refusals and important phase/reload events. Keep total-check and omitted-entry accounting accurate.

3. **Make covered reloads explicit: agree.** The current size-only exemption does not establish that a reload was included in the enclosing workspace model, nor consume an allowance across repeated reloads. Default to no exemption; permit one only with a specifically modeled, consumable allowance and tests for cumulative reloads. Claude identifies this as latent, not a demonstrated failure in this inlet trial.

4. **Single-frequency qualification: agree.** Current shadow observations intentionally share only within a single-frequency request. Run qualification cases individually. One successful next-mesh comparison in this trial is not broad qualification.

5. **Compare construction quantities, but label them correctly.** `peak_accounted_build_bytes / inverse_construction_bytes` is a modeled/accounted ratio. It is not a measured peak ratio. Record it and any underestimate flag separately from externally sampled process peaks; process growth and whole-process peaks also have different baselines. Neither should silently become an admission discount.

6. **Full regression coverage before push: agree.** The 260-test run was targeted. Broader shared-memory accounting paths need validation after the follow-ups, followed by the same end-to-end A/B to check overhead and accuracy.

Claude's statement that the prerequisite is completely met is too strong if read as a universal allocation guarantee. Explicit workspaces remain modeled, the covered-reload issue needs repair, and external processes can change headroom. The detailed audit itself acknowledges these limits. Keep forecast corrections disabled while these issues and independent tight-memory qualification are addressed; zero underpredictions in a small sample alone does not prove a general upper bound.

## Suggested next implementation

Repair explicit reload accounting and report retention; reduce repeated OS/worker queries without weakening per-allocation capacity accounting; add clearly labeled construction comparison metadata. Then run broad regression coverage and repeat the inlet A/B. Keep compressed as default, dense as a manual override, and forecast correction in shadow mode throughout.

`verification.json` records timing arithmetic, corrected build counts, bitwise field checks and matching baseline-source hashes. The current implementation also matches all ten saved source/test hashes from the previous handoff. Claude's report and trial artifacts were left unchanged.
