# Memory calibration and implementation — 29 October 2026

Implements the recommendations in [the review of Claude's audit](../claude_followups_review_20261029/README.md), starting from `b233c192fa779be738f2e418172e84a5fc3460aa`. Scope: compressed 2D CPU memory accounting, worker lifecycle, HPC submission forecasts and evidence calibration. Compressed remains the default; dense remains an override.

## Findings and decisions

The previously reported 18–26% slowdown did not reproduce in an alternating comparison. The old mean was **156.61 seconds**, and the new mean **156.82 seconds**, a **0.13% difference**. All fields were identical. This does not establish the cause of the original slowdown; the unsupported explanation based on counting spool progress notifications remains rejected.

Releasing the idle tile-worker team when the admitted mesh switches to hierarchical assembly reduced the observed peak process-tree RSS from **2.284 to 1.883 GiB** and private commit from **2.847 to 2.276 GiB** in the ordinary 12-foot inlet comparison. It also recovered **1.894 GiB of forecast allowance** for retained matrix/factor storage. Those are different quantities: recovered reservation is not measured physical memory freed. The candidate finished in 154.49 seconds versus 157.25 for its baseline, but one comparison with less monitoring work after worker closure is insufficient to claim a general speedup.

Active-worker allowances are unchanged. Profiles cover two and four workers on the ordinary inlet and eight on the narrow inlet. Busy-stage USS, private commitment, process lifetime peak private commitment and serialized payload are recorded separately. These samples do not exhaust future material, cache, tile and serialization peaks. In particular, the two-worker solve took 225.75 seconds; shrinking the worker team solely to reduce idle RAM would sacrifice useful concurrency.

## Implementation

1. `execution/memory.py` reads Windows' actual system commit limit and current commitment through `GetPerformanceInfo`. `execution/memory_budget.py` recognizes changes to that backing limit while preserving the original 90% physical-memory allowance and explicit/scheduler caps. It never treats a reduction in current commitment as new reservation capacity. The cohort update and aggregate reservation allocation occur under the existing lock. Held reservations are not refunded when the OS limit contracts or a parent cap tightens, because already allocated bytes may still exist. Live physical and commit checks remain active. Missing probes do not authorize additional capacity.
2. `compressed/runtime.py` closes an idle tile-worker team before an actual hierarchical mesh admission. The forecast is then recalculated without that obsolete team. Speculative estimates do not close workers, busy teams are preserved, and tile fallback/reuse follows the existing worker admission and recreation path. No active-worker allowance constant was reduced.
3. The combined historical regression set exposed an HPC planning regression in the preceding implementation: submission estimates called the local RAM budget. Submission forecasts now use a host-independent retained-payload forecast (the historical 2 GiB value for automatic storage, or an explicit configured value). Actual compute-node admission still sizes automatic storage from the real allocation and phase workspaces. `submission_planning` is an internal call parameter, not a user-facing solver option.

Windows' pagefile was already system-managed. No OS setting was changed. New capacity is usable only after Windows reports that it exists; this does not force pagefile growth or guarantee that every workload reaches 90% of available RAM. An already constructed factor retains its original storage cap; later admissions can use newly observed capacity.

Microsoft documents the current commit limit as a soft limit that can grow or shrink, with commitment charged before pages are touched: [PERFORMANCE_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-performance_information). See also [Windows pagefile behavior](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/introduction-to-the-page-file).

## Evidence and reproducibility

- `compare_revisions.py` ran old/new/new/old with four workers and four BLAS threads. Old is `63429ba`, new is `b233c19`. Snapshots have recorded source and identical native-DLL hashes in `snapshot_manifest.json`. The same sampling harness and external guards apply to both versions. No regression test suite or other agent-launched benchmark ran concurrently with these valid studies.
- The sampler ran approximately every 250 ms; the process-tree guard ran separately. Snapshot/limit timings are nested and cannot be added as independent wall time. The sampler consumed approximately seven seconds in aggregate across its background calls per baseline, also not an exclusive wall-time charge. Process CPU, host load, frequency and worker lifecycle are saved.
- Two early harness attempts are explicitly excluded in `aborted_snapshot_trials.json`: the first lacked untracked native DLLs, and a second overlapped it before normal Windows process access allowed cleanup. Their raw logs are retained; neither enters timing or certification conclusions.
- The idle-release candidate uses an audit-only wrapper around the old code. Final trials exercise the production implementation directly. Ordinary/narrow PEC and representative dielectric inlets use 15 GHz, both polarizations and 361 observation angles. Each result must pass quality and mesh certification and match the earlier saved fields exactly.
- `validate_combined.py` runs the union of test files from both prior audits plus new capacity and worker-transition tests. The first union run exposed two stale fallback forecast fixtures and the actual HPC planning regression. The fixture now includes the phase-workspace data required by real forecasts and asserts envelope activation. Failed and focused intermediate results are preserved separately; `validation_results.json` is the latest combined run.
- `pressure_study.py` touches real memory under both solver checks and an external time/physical-memory guard. It records actual Windows commitment, limit and physical availability alongside each reservation. A touched-memory ramp is not a full large numerical solve. Synthetic tests separately exercise verified growth, shrinkage, unknown probes, retained reservations and concurrent callers.
- `summarize.py` rebuilds the final summary from raw results. `source_hashes.json` identifies validated changed files. All 85 historical evidence hashes remain unchanged.

## Final validation and observed pressure limits

**621 tests and 114 subtests passed**, across 44 affected files. All nine numerical study runs passed quality and mesh certification and reproduced both polarization fields exactly. The final production trials were:

| Case at 15 GHz | Request cap | Wall time | Peak tree RSS | Peak tree private commit |
|---|---:|---:|---:|---:|
| Ordinary inlet, 4 workers | 3.1 GiB | 154.83 s | 1.847 GiB | 2.259 GiB |
| Representative dielectric inlet | 8 GiB | 193.19 s | 3.991 GiB | 4.357 GiB |

The first pressure ramp had 16.624 GiB initially available physical RAM, 14.876 GiB available commit and a 13.389 GiB reservation. It touched approximately **80.16%** of initially available physical RAM, including a 64 MiB allocator margin below the reservation. The 85% and 90% targets were not reached. A second ramp held its bounded allocation for ten seconds to allow time to observe growth: it reached **80.23%**, with no additional capacity reported. The system commit limit stayed at **33.103 GiB in both trials**. The pagefile remained system-managed and allocated at 2048 MiB; no OS setting was changed.

Thus the new growth path is covered by synthetic/native-API regression cases, but **real automatic commit-limit growth was not observed here**. The solver still stopped at its deliberate initial commit reserve in these runs. This does not prove that Windows could never grow the pagefile, nor justify bypassing the commit reserve. The patch will recognize future observed growth; it does not by itself deliver 90% physical utilization on this PC under these conditions. Raw evidence for the ten-second variant is in `pressure_hold/`, reproducible with `pressure_study.py --hold-growth`.

The external 50 ms monitor and the allocation-event snapshots can report different peak values during a fast ramp; use each as a sampled observation, not an exact continuous high-water mark. The ramp recorded no external guard violation and released its allocations on exit.

## Remaining scope

No full numerical solve consuming 90% of initial available physical RAM has been qualified by this study. The final inlet trial exercises a tight explicit 3.1 GiB request allowance, and the dielectric trial adds representative material coverage. Arbitrary larger, more intricate inlet geometry can still hit rank growth, workspace or convergence limits. The code retains those checks; the present measurements do not justify reducing them or promising an arbitrary 12-foot geometry fits.
