# Review of Claude's calibration handoff — 29 October 2026

Reviewed [Claude's report](../../Claude_audit/review_of_codex_memory_calibration.md) against `50d2c64820def24fe9e993cbeef794074fc79998`, the current source and saved evidence. The user's subsequent clarification governs the recommendation: **90% available RAM is a soft goal, not an acceptance threshold.**

The implementation should be retained. Claude's acceptance of idle-worker release, synchronized commit-capacity accounting and independent HPC submission forecasts is supported by the code and existing validation. This review found no new reproduced implementation defect requiring a patch. Its proposed next steps need qualification: a pagefile change and a near-90% solve are not required merely because the pressure ramps reached about 80%.

## 1. Timing: the historical slowdown is not explained conclusively

Claude's statements that the slowdown is definitively the PC and that the code is cleared are too broad. The controlled comparison supports the narrower conclusion that **the tested ordinary-inlet workload did not reproduce a timing regression between `63429ba` and `b233c19`**: 156.611 versus 156.818 seconds, a 0.132% difference, with identical fields.

The old revision's earlier result was 124.022 seconds, so the cross-session difference is real: 26.277%. Geometry requests and numerical options match, with a different scratch location. But the measurement harness also changed. The earlier `trace_solve.py` wraps memory/storage/factor calls and logs progress events; the later `study.py` uses different wrappers plus a background sampler that enumerates child processes, requests full memory information and records host CPU data. Both sides of the alternating A/B use that same later instrumentation, which supports their relative comparison. It does not isolate the cause of the difference from the earlier session.

The roughly seven seconds spent inside background sampling calls cannot simply be subtracted from wall time or treated as a bound on its impact. Those calls overlap computation and can interact with other work. Power, background load, temperature, scanning and instrumentation remain hypotheses. The saved fixed 4700 MHz reading does not establish actual effective clock behavior or throttling.

One additional old-code dielectric run would add evidence, but would not by itself prove the cause of the dielectric timing shift. If the slowdown matters in routine use, use repeated comparisons with identical instrumentation and workload, or controlled profiling. Existing same-session A/B evidence remains useful; Claude's statement that all future comparisons are unreliable is too sweeping.

## 2. Pagefile: a conditional capacity estimate, not a measured fix

The held trial confirms no observed commit-limit growth during its ten-second hold. Sampled commitment was approximately 95.12–95.33% of the observed limit, which remained 33.103 GiB. That supports the trial-specific observation, not the statement that growth cannot happen automatically on this PC or requires another program to consume the remaining commit.

Microsoft describes automatic growth of system-managed pagefiles around 90% system commitment, subject to conditions including available disk space. The saved trial does not explain why no growth was observed. There is no evidence here that only another process can trigger growth. [Microsoft pagefile documentation](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/introduction-to-the-page-file).

The proposed 4–6 GiB pagefile minimum was **not tested**. At the held trial's initial snapshot, available physical RAM was 16.763 GiB and available commit was 15.014 GiB. Their difference is approximately **1.749 GiB**. If actual commit capacity increased by that amount while other conditions stayed equal, the existing 90% physical allowance would become the tighter reservation constraint. This arithmetic is reasonable, but it is not a validated universal pagefile size, a measured fix, or a guarantee that a particular large solve fits.

Claude's promise of "no paging" is also unsupported. The solver's memory checks do not lock its pages in RAM or control other processes. Windows manages working sets and can trim pages; keeping a physical reserve does not guarantee no paging. [Microsoft working-set documentation](https://learn.microsoft.com/en-us/windows/win32/memory/working-set).

Given the soft utilization goal, leave OS settings unchanged unless a useful real workload is demonstrably blocked by commit headroom. The current 80% observations alone do not justify an OS adjustment or another near-90% qualification exercise.

## 3. Worker allowance: keep it, but do not claim it can never bind

Leaving active-worker allowances unchanged is sensible. Releasing idle teams already removes their reservation from subsequent hierarchical meshes without weakening the allowance for future active allocations.

However, tile meshes are not necessarily small or incapable of becoming memory-limiting. `compressed/hmatrix.py:unsupported` retains the tile route for unsupported configurations and thin dielectric layers with magnetic contrast; hierarchical rejection can also lead to tile fallback on a large system. `compressed/runtime.py:admit_tile_fallback` explicitly reprices its workers and workspaces and refuses the fallback when they do not fit. That behavior contradicts the report's universal claim that tile meshes are never memory-binding. Revisit calibration if representative tile/fallback workloads actually hit this limit, rather than weakening the allowance now.

Claude's worker table also uses the sum of individual process lifetime peak private commitments, sampled while the pool is busy, rather than simultaneous private commitment alone:

| Trial | Maximum sampled simultaneous private commit | Sum of individual lifetime peaks | Reserved allowance |
|---|---:|---:|---:|
| 2 workers | 0.350 GiB | 0.364 GiB | 0.947 GiB |
| 4 workers (`ab_new_1`) | 0.647 GiB | 0.704 GiB | 1.894 GiB |
| 8 workers, narrow inlet | 1.284 GiB | 1.434 GiB | 3.792 GiB |

These are useful distinct measurements. Individual process peaks need not occur simultaneously, and sampling can miss brief changes. Neither column exhaustively bounds future material, serialization, cache or tile requirements. The conclusion to keep the allowances remains appropriate.

## Recommended next steps

1. Keep the current implementation and active-worker allowances. No backend-picker expansion, reserve relaxation or OS change is indicated by this review.
2. Prioritize representative large concave geometries and material configurations when assessing practical capacity. Record the exact phase, forecast, live RAM/commit and field certification if a real solve is refused; distinguish a false estimate from an allocation that genuinely does not fit.
3. Investigate performance only when repeatable differences matter to actual runs. Start with measurements using the same harness and read-only process/power observations. Do not add Defender exclusions based solely on the untested scanning hypothesis.
4. Treat pagefile sizing as a conditional response to a demonstrated commit bottleneck in useful work. Reaching a particular RAM percentage is not the purpose of the solver.

## Verification scope

[verification.json](verification.json), reproducible with [verify_review.py](verify_review.py), confirms all nine validated changed-source hashes and all 85 historical evidence hashes still match. The saved records contain 621 unique passing tests, 114 additional subtest reports and nine certified numerical study runs with identical fields. These are prior results checked during this review, not newly rerun tests or solves. No production code, OS setting or prior evidence was changed, and nothing was committed or pushed by this review.
