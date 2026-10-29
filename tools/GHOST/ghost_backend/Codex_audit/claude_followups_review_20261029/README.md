# Review of Claude's memory-follow-up audit — 29 October 2026

Reviewed [Claude's latest report](../../Claude_audit/review_of_codex_memory_followups.md) against commit `b233c192fa779be738f2e418172e84a5fc3460aa`, the code and saved numerical/pressure evidence. The implementation source hashes still match the validated files. This review makes no production or operating-system changes and runs no new solves or regression suite.

Claude's acceptance of the three reproduced fixes is supported. The aggregate reservation counterexample, incremental reload cases and workspace-based storage calculation are addressed. Its broader assertion that all remaining limits are outside the solver is stronger than the evidence supports. Several recommendations need correction or qualification.

## 1. The pagefile is already system-managed

A read-only Windows configuration query during this review returned `AutomaticManagedPagefile=true`, an allocated pagefile of 2048 MiB, current usage of 72 MiB and peak usage of 84 MiB. Physical RAM reported by Windows was 33,396,543,488 bytes. These are current observations, not reconstructed settings from the earlier trials; the raw snapshot is in [pagefile_snapshot.json](pagefile_snapshot.json).

Therefore switching to system-managed paging is not an actionable change on this PC. Nor does the ramp demonstrate that the OS exhausted all commitment: it stopped at the solver's **90% of initial available commit** reservation. About 1.46 GiB was deliberately reserved, and the second ramp retained allocator margin within that reservation.

The code freezes both the request ceiling and its shared reservation group's capacity. If Windows increases its commit limit later, `limit()` can observe larger live headroom, but the original stable ceiling still wins. Microsoft documents automatic pagefile growth near 90% system commitment when sufficient disk space is available. That makes an initial commit snapshot potentially conservative; the saved ramp did not measure whether automatic growth happened or would have happened. [Microsoft: Introduction to page files](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/introduction-to-the-page-file).

The precise conclusion is: **the initial-commit-based admission policy was the binding constraint in those trials**, not that Windows had proven an immutable 79–80% physical utilization ceiling. A larger preallocated pagefile could increase the initial allowance, but it is not established as the only solution, and no size recommendation or OS change is warranted from these records alone.

Claude's verbal formula also needs correction. Remaining system commit is the system commit limit minus current committed memory; the limit is approximately physical RAM plus pagefiles. Starting with *free* RAM and subtracting all commitment again is not the correct calculation. The implementation reads the Windows API rather than using that formula. [Microsoft's definition](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/introduction-to-the-page-file).

## 2. The claimed increase in spooling is a measurement error

The ordinary-inlet progress log contains 5 spool-write notifications before and 11 afterward. Those are sampled UI/progress events, not operation counts. `execution/metrics.py` publishes at most every 0.5 seconds during ordinary progress updates and reports total elapsed run time; its separate `stage_calls` and `stage_seconds` record completed stage invocations.

The actual saved profiles show:

| Ordinary inlet | Previous run | Follow-up run |
|---|---:|---:|
| Recorded spool-write calls | 320 | 320 |
| Cumulative spool-write time | 0.153 s | 0.173 s |
| Recorded spool-read calls | 2 | 2 |
| Cumulative spool-read time | 0.789 s | 0.831 s |
| Spool-write progress notifications | 5 | 11 |

Consequently, the report's claim that tighter storage caused writes to increase from 5 to 11 and cost 2.6 to 5.7 seconds is unsupported. The narrower inlet also has unchanged write/read call counts; the dielectric profiles contain no such spool stages. A smaller allowance can cause more disk activity in other workloads, but these trials do not demonstrate that effect.

## 3. The slowdown is real; its cause is unresolved

Wall times increased by 25.64% for the ordinary inlet, 25.07% for the narrow inlet and 17.85% for the dielectric inlet. Fields remained identical. Several substantial computation stages slowed as well, consistent with host contention, but that does not prove the cause or exonerate all implementation overhead.

The saved profile marks stage times as inclusive and potentially overlapping. Claude's roughly 65-to-83-second assembly comparison is close to the hierarchical assembly stage, not a complete exclusive accounting of all operator work. Do not add nested stage times or infer work counts from progress notifications.

A controlled A/B comparison remains useful. Prefer repeated alternating runs, with the same geometry, options, worker counts, monitoring and temperature/load conditions, over one old/new pair. Compare numerical work, exclusive wall time, actual stage calls, process CPU time and memory-sampling overhead. The current review does not launch that benchmark.

## 4. Worker calibration is worthwhile, but saved USS is insufficient

The last 16 recorded worker samples in the new ordinary-inlet run show about 0.298 GiB maximum aggregate USS and 0.567 GiB private commit, versus roughly 1.89 GiB retained worker allowance. This is a promising profiling target. It does not justify replacing the allowance with 0.298 GiB: the samples are a bounded tail of the request, not guaranteed busy-stage high-water measurements.

The allowance covers process baseline, kernel tables, tile destinations, a 64 MiB moment cache per worker, and serialized geometry/oracle payload growth. Calibration must measure active assembly across representative sizes/materials, worker counts and mesh transitions, including commit as well as residency and cache/serialization peaks. The dielectric trial has no retained tile-worker samples; it is not an independent validation of a smaller tile-worker allowance.

A useful optimization study should also compare releasing idle workers before larger factorizations with retaining them for later mesh assembly. That trade-off can recover memory without treating an observed idle footprint as a future allocation bound. No allowance was reduced in this review.

## 5. Other qualifications

The 22 GiB payload example is arithmetic conditional on 28 GiB available RAM, sufficient commit capacity, no tighter cap and about 3.145 GiB workspace: `0.9 × 28 − 3.145 ≈ 22.055`. It is not a measured capacity for arbitrary large geometries. Workspace and inverse ranks grow with the actual system.

`ui/solver.py` guards overlapping solve/density jobs within a solver widget. This supports Claude's conclusion for the normal one-job GUI workflow, but it is an instance guard, not proof that every possible same-process embedding cannot overlap requests. The conservative overlap accounting remains appropriate.

391 results are not a rerun of the earlier 467. Both were targeted validation sets, not the entire repository suite. Fourteen earlier test files were absent from the newer set, while seven new files were included; the exact lists are in [verification.json](verification.json). For a subsequent accounting or scheduling change, rerun the combined affected set, especially scheduler/GUI integration, before pushing. This evidence gap is not itself a reproduced defect.

## Suggested next order

1. Run a controlled timing comparison to explain the 18–26% wall-time difference. Discard the unsupported increased-spooling explanation.
2. Profile worker busy-stage residency, private commit, caches and payload growth; compare idle-worker release versus reuse.
3. Record system commit limit, live commitment, pagefile allocation and the stable solver ceiling together during a bounded pressure trial. Investigate whether retaining an initial commit ceiling needlessly prevents useful automatic growth. Any relaxation must preserve physical headroom and synchronized aggregate reservations; do not simply remove the commit guard.
4. Only then choose between a justified pagefile adjustment and a solver policy change, and run a complete numerical solve near the desired physical utilization.

The fixes should be retained. No newly reproduced numerical correctness failure was found in this review. The best immediate follow-ups are measurement and calibration, rather than changing an already system-managed pagefile on assumption.
