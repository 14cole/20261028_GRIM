# Implementation handoff for Claude — memory calibration, 29 October 2026

Please audit the implementation and evidence in [Codex's report](../Codex_audit/memory_calibration_20261029/README.md), following the corrections in [the review of your prior report](../Codex_audit/claude_followups_review_20261029/README.md). The base revision is `b233c192fa779be738f2e418172e84a5fc3460aa`; the new commit containing this file carries the implementation. Exact changed-source hashes are in the audit folder.

## Implemented changes

- Release obsolete idle tile-worker processes before admitting a hierarchical mesh, then reprice the workspace. Busy teams and speculative forecasts are preserved. Later tile fallback/reuse recreates the team through existing admission. No active-worker growth allowance was reduced.
- Recognize **observed Windows system commit-limit changes**, independently of current free commit. Growth is shared through the locked cohort capacity, bounded by initial physical capacity and request/scheduler caps. Existing held reservations remain held after contraction; current admission tightens and peers cannot spend already promised bytes. Unknown probes never justify growth. Current live physical and commit checks remain separate.
- Restore host-independent HPC submission forecasts. The combined historical suite caught a real regression from the preceding change: the planner queried the submitting PC's RAM. Automatic submission forecasts use the historical 2 GiB payload estimate; compute-node admission still uses allocation minus forecast workspace. The flag is internal and adds no user-facing option.

## Evidence to inspect

- Controlled old/new/new/old inlet comparison: **156.61 versus 156.82 seconds on average (+0.13%)**, identical fields. This does not reproduce the earlier 18–26% slowdown, and it does not prove its original cause.
- Idle-release comparison: process-tree RSS **2.284 → 1.883 GiB**, private commit **2.847 → 2.276 GiB**, and **1.894 GiB forecast allowance recovered**. Do not equate the forecast allowance with measured RAM freed. The timing improvement is a single candidate observation, not a general speed claim.
- Busy-stage worker samples cover 2/4/8 workers, ordinary/narrow PEC geometry and mesh transitions. Keep private commit distinct from USS and sampled peaks distinct from unsampled high-water risk. The material trial does not establish a smaller tile-worker allowance.
- Latest combined regressions: **621 tests and 114 subtests passed**, across 44 affected files. This combines both previous audits' coverage and the new tests; it is not the complete repository suite. Intermediate failed reports are retained and labelled in the main report.
- Nine successful numerical study runs, including the controlled repeats and final production trials, are enumerated by `study_summary.json`. The final production inlet uses a tight 3.1 GiB cap; the dielectric uses 8 GiB. Require quality/mesh certification and exact field equality in each saved result.
- Two touched-memory pressure ramps reached **80.16% and 80.23%** of initial available physical RAM. The second included a ten-second hold. Windows reported the same **33.103 GiB commit limit** throughout; the pagefile remained system-managed at 2048 MiB. Real OS growth and 90% physical utilization were not demonstrated. The ramps record actual system limit, commitment, physical headroom and reservation together. Read `study_summary.json`, `pressure_events.jsonl`, `pressure_accounting.json` and before/after pagefile configuration. It is not a complete numerical solve at 90% physical utilization. No OS setting was changed.
- Historical evidence integrity: all 85 input hashes still match. Two invalid early benchmark attempts (missing native DLLs / overlapping restart) are explicitly excluded; their raw logs remain available.

## Review priorities

1. Check that commit-limit growth cannot be counted twice across concurrent requests, and that contraction does not refund memory still allocated. Check explicit/scheduler caps, missing probes and initial snapshot coherence.
2. Check that worker release is limited to genuine hierarchical admission and that fallback reprices and recreates workers safely.
3. Check both HPC estimate entry points avoid local RAM/ledger probes, while runtime admission still reads actual node allocation.
4. Separate measured memory savings from reserved allowances and hypothetical capacity. The full 90%-of-initial-available numerical solve remains unqualified; avoid describing a pressure ramp or a small capped solve as that qualification.
5. Treat stage timings as inclusive and progress notifications as sampled. Compare real `stage_calls` if examining spooling.

No persistent solve history, new backend selector, OS paging change or relaxed numerical certification was added.
