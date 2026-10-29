# Resource efficiency follow-up — 29 October 2026

The objective is useful solve throughput and capacity, not a prescribed RAM percentage. This work follows [the review of Claude's handoff](../claude_calibration_review_20261029/README.md). Base revision: `50d2c64820def24fe9e993cbeef794074fc79998`.

## Implemented correction

A hierarchical-to-tile fallback can retain live memory that its structural geometry/worker forecast does not explain, such as native caches. Previously, `admit_tile_fallback` sized automatic storage first and added this extra residency afterward. It could then refuse the adjusted forecast without considering a smaller automatic storage allowance.

`planned_forecast` now accepts the measured residency for this admission, includes its excess in the phase workspaces before choosing automatic storage, and carries it into `process_geometry_bytes` for later reload checks. Explicit storage settings remain explicit; excessive non-storage workspaces still refuse admission. Speculative forecasts do not replace the active plan. Numerical accuracy checks and actual operator/factor storage limits remain in force.

The synthetic reproduction has a 6 GiB reservation and 1 GiB of extra live residency. Previously it refused at 6.251 GiB. It now grants a 2.108 GiB payload allowance instead of 3.108 GiB and admits a 6.000 GiB forecast. This demonstrates a corrected admission calculation, **not** proof that an arbitrary numerical inverse will fit the smaller cap. The real factor must still fit and pass certification. `fallback_before.json`, `fallback_after.json` and `reproduce_fallback.py` preserve the evidence.

## Throughput and realistic capacity study

`study.py` runs serial isolated solves. The throughput comparison uses the same 12-foot-long, 3-foot-wide inlet at 15 GHz, both polarizations, 361 observation angles, adaptive mesh certification and a 12 GiB request cap. Profiles alternate four/automatic/automatic/four. The four profile sets assembly and BLAS to four; the automatic profile uses the existing production defaults. Thus this compares complete execution profiles, not worker count alone.

The host is an AMD Ryzen 7 9800X3D with eight physical cores and sixteen logical processors, using the Balanced power plan. These settings were read, not changed. Automatic execution initially reserves eight assembly threads and two BLAS threads, with the existing ability to use available allocated cores for appropriate BLAS phases. No new tuning mode or performance-history cache was introduced.

The same run harness then tests a more intricate 12-foot by 3-foot dogleg contour with multiple concave corners: PEC, moderate dielectric (relative permittivity 4−0.04j, permeability 1), and a high-contrast lossy magnetic stress case (permittivity 101.19−11.88j, permeability 3.45−3.47j). The stress case is not a typical low-contrast material. All requests use 15 GHz and unchanged certification requirements. Failed cases retain the phase, error, active plan and memory-accounting record so numerical limits can be distinguished from memory refusal.

Monitoring is the same across comparisons: external process-tree RSS/private commit sampled every 250 ms, normal progress events, and parent CPU time. No heavy regression suite runs concurrently with these studies. A 14 GiB external process-tree guard, 2 GiB available-memory floor and per-case time bound protect the host during exploratory cases; those are trial guards, not new production policies. Tree RSS can double-count shared pages, so it is an approximate memory observation. Stage durations can overlap and should not be summed as exclusive time.

The automatic profile was already the default. Any demonstrated speed advantage over the four-worker control is evidence to retain that default, not a speedup attributable to the fallback-sizing patch. An unused CPU core or free memory is not inherently wasted if more concurrency or caching would slow the solve; measured throughput and correct results determine the useful allocation.

## Validation and artifacts

Focused regressions initially passed: 107 tests, including the new fallback-sizing cases, request ownership, live pressure, worker transitions and explicit caps. `validate_combined.py` runs the combined affected suite after all numerical cases finish. `tested_source_hashes.json` records the exact changed source/test bytes used by the trials. All older results remain untouched.

Raw numerical cases are in `runs/`; per-case `request.json`, `result.json`, `metadata.json` (successful numerical execution), `accounting.json`, `last_plan.json`, stage events and process samples preserve the evidence. The final summary distinguishes certified passes, genuine refusals and external guard stops. No claim of universal optimality or arbitrary-geometry capacity follows from a finite study.

## Measured outcomes

Automatic execution averaged **117.70 seconds** against **149.81 seconds** for four assembly/four BLAS threads: **32.10 seconds saved (21.43%)**. The repeats were close: 117.90 and 117.50 seconds versus 149.88 and 149.73 seconds. All four inlet runs certified. The four-worker controls matched the saved reference fields exactly; automatic runs differed by at most 4.13e-16 relative error, consistent with floating-point roundoff. The main observed stage reduction was hierarchical assembly, about 80.3 seconds in the first control versus 59.0�59.3 seconds in the automatic runs; those inclusive stage timings are not an exclusive decomposition of wall time.

| 15 GHz case | Outcome | Wall time | Peak tree RSS | Peak tree private commit |
|---|---|---:|---:|---:|
| inlet_four_1 | Certified | 149.88 s | 1.879 GiB | 2.273 GiB |
| inlet_auto_1 | Certified | 117.90 s | 1.875 GiB | 2.672 GiB |
| inlet_auto_2 | Certified | 117.50 s | 1.867 GiB | 2.689 GiB |
| inlet_four_2 | Certified | 149.73 s | 1.835 GiB | 2.246 GiB |
| dogleg_pec15 | Certified | 65.64 s | 1.821 GiB | 2.643 GiB |
| dogleg_dielectric15 | Certified | 370.85 s | 6.017 GiB | 6.875 GiB |
| dogleg_magnetic15 | Panel-count limit | 5.35 s | 0.388 GiB | 0.594 GiB |

The metal dogleg agreed with its earlier reference to at most 5.43e-13 relative field error. The moderate-dielectric dogleg independently passed the production field-quality and mesh-convergence gates; it has no independent external reference in this study. Its quadratic and cubic solves took about 150.3 and 220.5 seconds. The higher cost is material/operator work with independent certification, not evidence of a memory refusal.

The magnetic stress case exceeded the request's **100,000-panel limit** during geometry preparation after 5.35 seconds. No operator assembly or factorization was attempted, and no memory-admission failure was recorded. This is a configured discretization limit, not measured proof of RAM exhaustion or proof that relaxing the limit would fit. That material/geometry combination remains unqualified at 15 GHz. If it is an intended workload, the next specific study is material-aware discretization and capacity with unchanged accuracy checks, rather than changing the pagefile or filling more RAM.

Decision: retain the existing automatic CPU defaults and active-worker allowances, keep the fallback-sizing correction, and prioritize cases with demonstrable premature refusals or costly repeated numerical work. No universal optimum is claimed. The current controls do not establish a speedup caused by the source patch itself; they show that manually limiting this machine to four workers leaves useful throughput available.

Record-label correction: the harness originally labelled the published linear-node count as `system_dofs`. The saved result keys and harness now use `linear_node_count`; no values, numerical results or timings changed. Raw worker logs retain the original printed label.

Final regression result: **624 tests and 114 subtests passed** across the 45 combined affected test files. Six numerical studies certified; one high-contrast study was stopped by its configured panel limit. The validated changed-source hashes match, and all 85 historical evidence hashes remain unchanged. No full-repository-suite claim is made.
