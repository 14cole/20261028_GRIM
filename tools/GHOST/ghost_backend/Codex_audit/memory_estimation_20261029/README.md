# Memory estimation audit — 29 October 2026

The solver can reject work while substantial RAM is still available. I reproduced a specific accounting problem in both compressed factor constructors, found several additional restrictions, and traced a real 12-foot inlet solve. Supporting 90% of available RAM is a reasonable target, but the current implementation does not apply that target consistently throughout a solve. Changing the top-level percentage alone would not fix it.

This audit adds evidence and recommendations only. Production code and accuracy gates were not changed. It audits the current working tree, including the preceding compressed-default and memory-recovery changes, rather than just Git HEAD `5460aa2`. The historical error described by the user was not accompanied by its original log, so these are demonstrated mechanisms that can explain that behavior, not a claim to have identified that particular incident.

## What was verified

- Traced physical-memory detection, solve admission, compressed payload limits, operator/inverse construction, retained partners, worker allowances, refinement, dense-copy fallback, and desktop/local/HPC scheduling.
- Reproduced shrinking budgets and a false storage refusal using the actual `CompressedFactor` and `HMatrixFactor` constructors. Large byte counts were synthetic metadata; inverse construction was disabled in these accounting probes.
- Built and reloaded a small real spooled operator, verifying its matrix product and its storage accounting.
- Analyzed 28 historical records with phase forecasts and external process-tree monitoring. Only fixed-compressed cases are used for the forecast/RAM comparisons below. Adaptive/mixed runs can contain forecasts for a backend they did not execute; those ratios are explicitly flagged as unsuitable for calibration.
- Ran a new instrumented, certified 15 GHz solve of the representative 144 × 36 inch PEC inlet, all 361 requested angles, using the current public compressed default. No RAM limit, availability reading, backend decision, or numerical tolerance was altered by the instrumentation.
- Ran the existing memory-safety, compressed-memory, compressed-recovery, hierarchical-resource and compressed-projection suites: **66 tests passed**. These do not cover all the accounting problems reproduced by this audit.

Evidence: [budget and historical analysis](evidence.json), [real-run summary](live_summary.json), [raw run](live_inlet15/), [test results](validation_results.json). Reproduction commands, from the backend directory: `python Codex_audit/memory_estimation_20261029/audit.py` and `python Codex_audit/memory_estimation_20261029/summarize_live.py`. `trace_solve.py` refuses to overwrite its existing run directory.

## 1. Automatic storage shrinks after its own allocations — highest priority

`compressed/runtime.py:26–55` sets automatic retained storage to 60% of `_solve_memory_limit_gb()`. That solve limit normally uses 90% of **currently** available memory. The storage function is called again when constructing an inverse, after assembly has consumed RAM. `compressed/factor.py:40–43` then subtracts the existing operator and partner from this newly reduced allowance. `compressed/hmatrix_factor.py:102–107` uses the same constructor accounting.

Assume 24 GiB is initially available, no external memory pressure, and no lower explicit or scheduler cap:

| Own operator already resident | RAM still available | Newly computed storage cap | Room left for inverse | Room under the original storage cap |
|---:|---:|---:|---:|---:|
| 0 GiB | 24 GiB | 12.96 GiB | 12.96 GiB | 12.96 GiB |
| 4 GiB | 20 GiB | 10.80 GiB | 6.80 GiB | 8.96 GiB |
| 8 GiB | 16 GiB | 8.64 GiB | 0.64 GiB | 4.96 GiB |
| 10 GiB | 14 GiB | 7.56 GiB | **Constructor refuses** | 2.96 GiB |

The last row actually raises `No compressed inverse storage remains.` in both constructors. It does not mean the computer has run out of physical RAM. This reproduction proves inconsistent accounting; it does not prove that an arbitrary 10 GiB operator's inverse and transient workspaces would fit or pass numerical checks.

Even the legitimate 60% payload share can be unnecessarily restrictive when the next phase's workspace is small. Conversely, eliminating it without budgeting construction workspace could allow a real overrun. Establish a stable request-owned budget first, then replace the fixed share with phase-specific allocations where measured evidence supports it.

## 2. Later admission mixes total peak with remaining free RAM

The main monostatic gate (`twod/solver.py:2458–2509`) compares a total phase forecast against a live available-memory limit. Its resident credit comes from `reusable_dense_bytes`; that helper explicitly returns zero for compressed execution (`twod/assembly/session.py:67–86`). Compressed operators, retained caches and workers can already be present at later polarization/refinement checks.

For example, a forecast of 18 GiB with 8 GiB already owned needs another 10 GiB. If 16 GiB is still free, comparing the whole 18 GiB against 14.4 GiB rejects it, although the incremental requirement fits and the 18 GiB total remains below an initial 21.6 GiB reservation. This is a code-path/arithmetic finding, not a reproduced full-size physical solve.

Some paths already handle residency: dense residual-copy admission, hierarchical-to-tile fallback, and optional preconditioner upgrades. Their conventions differ, however. Blindly passing whole-process RSS everywhere is not a sufficient fix: it includes unrelated work in a shared process, and worker reservations are not measured resident bytes. It could give the solve credit for memory it does not own.

## 3. Disk payload is still charged against retained RAM capacity

`SpooledOperator.store_tile` writes and removes numerical tile arrays, but keeps their byte count in `operator.bytes` (`compressed/polarization_cache.py:27–38`). Paired assembly subtracts this count from its common payload allowance, and the runtime passes it onward as `reserved_partner_bytes` during factorization. Thus a future partner's disk payload restricts the current inverse even while its numerical arrays are absent from RAM.

The real small-operator test recorded 70,208 charged partner bytes: 65,536 bytes were on disk, 4,672 were counted numerical metadata, and no partner tile payload arrays were resident. Reload reproduced the original matrix numerically. Python object overhead is additional; the metadata figure is not an RSS measurement.

This is a conservative capacity policy, not evidence that the operating system stores the disk payload twice. Split disk, resident and future-reload accounting. Credit the absent payload during the current solve, then admit the full load immediately before restoring it. Preserve cancellation, checksum and cleanup behavior. Merely subtracting disk bytes without adding reload admission would be unsafe.

## 4. Several independent margins restrict usable capacity

| Layer | Current behavior | Consequence |
|---|---|---|
| 2D solve limit | 90% of live available RAM, capped by explicit and parent allocation | Already nominally 90%, but residency semantics vary |
| Automatic compressed payload | 60% of that limit, with 16 MiB floor | Initially 54% of available RAM for retained payload; transient work uses the rest |
| Local batch driver | Minimum of 75% installed and 90% available, with 1 GiB floor | May prevent using the requested available-RAM target on a mostly idle machine |
| HPC driver | 85% of detected allocation, with 1 GiB floor | Separate cluster policy; changing desktop behavior should not silently change this |
| Desktop frequency workers | 1.25 × candidate forecast, plus 0.5 GiB per worker | Less concurrency than raw payload/RAM division suggests |
| Automatic legacy backend selector | Prefers forecasts fitting an additional 20% admission margin; can fall back to full budget | Not generally used by the current fixed-compressed public default, but still used in relevant planning/legacy paths |
| Local/HPC forecasting | 1.35 safety factor: whole dense estimate, sampled compressed operator only | These are not equivalent multipliers and should not all be removed together |
| Tile workers | 480 MiB plus payload allowance per retained worker | Includes interpreter, buffers and cache capacity; not actual current RSS |

Sources: `runs/local_twod_driver.py:98–100`, `hpc/twod_driver.py:147–149`, `hpc/scheduler.py:272–288`, `execution/frequency_sweep.py:170–180`, `execution/policy.py`, `compressed/tile_processes.py:18–26`, `compressed/worker_pool.py:145–159`.

For a 32 GiB host with 31 GiB available, the local driver permits 24 GiB, versus a 27.9 GiB target: **3.9 GiB unnecessarily excluded by that policy**. If only 24 GiB is available, the same driver already permits 21.6 GiB; the 75% installed limit is not binding in that case. This driver policy is separate from the desktop GUI's frequency-worker policy.

The 1 GiB scheduling floor has the opposite problem: with 0.25 GiB available it grants 1 GiB instead of 0.225 GiB. Also, a successful zero-available reading becomes `None` in the local scheduler and can bypass the live clamp entirely; the probe reproduced a 24 GiB local budget on a synthetic 32 GiB host reporting zero available. These are reasons to unify accounting, not simply relax checks.

## 5. Detection and error reporting need clearer distinctions

The 2D code consistently uses binary GiB despite historical `_gb` names. I did not find a general GB/GiB conversion error causing the reproduced failures.

However, zero available RAM and failure to detect RAM both become zero in the solve detector. With an explicit 12 GiB limit and a zero reading, `_solve_memory_limit_gb()` returns 12 GiB. A successful zero reading must remain distinct from an unavailable probe; explicit budgets must not override known exhaustion.

On Windows, the memory probe reads physical availability, while process metrics separately record working set and private commit. There is no corresponding live commit-headroom gate in the inspected 2D admission path. Physical availability and how much additional memory Windows can commit are separate constraints; Microsoft's [MEMORYSTATUSEX documentation](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/ns-sysinfoapi-memorystatusex) exposes both. [PrivateUsage](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex) measures private commit, not resident RAM. Add commit availability to diagnostics and allocation checks; do not treat it as extra physical RAM.

Errors should state the actual binding constraint: physical RAM, commitment headroom, explicit user cap, scheduler reservation, compressed payload cap, fixed query-workspace cap, or temporary-disk capacity. Several compressed exceptions currently give no required/allowed byte figures or reason for the limit. A failure to write a spool is a disk/I/O problem; a 16 MiB coefficient-query rejection is an algorithmic workspace bound. Neither should be described as the whole computer lacking RAM.

## Measured forecast conservatism

Historical successful, fixed-compressed runs:

| Representative 15 GHz case | Maximum saved phase forecast | Observed peak process-tree RAM | Observed private commit |
|---|---:|---:|---:|
| Ordinary PEC inlet, three repeats | 4.55 GiB | 2.25–2.28 GiB | 2.82–2.85 GiB |
| Narrow inlet, four repeats across two studies | 4.96 GiB | 2.58–2.61 GiB | 3.14–3.17 GiB |
| Moderate dielectric inlet, three runs | 6.62 GiB | 3.99 GiB | 4.35–4.36 GiB |

The new public-default inlet run reproduced the first row: **123.05 seconds, 2.282 GiB peak tree RAM, 2.846 GiB private commit**, with a 4.549 GiB maximum forecast. Quality and mesh certification passed. All complex output samples matched the earlier compressed reference exactly in this run.

The automatic payload cap was consulted 35 times and ranged from 8.09 to 8.83 GiB. This confirms it moves during real execution; host availability also responds to unrelated applications. The largest inverse forecast was 0.389 GiB versus a largest measured retained inverse of 0.237 GiB. The peak forecast included approximately 1.894 GiB of retained-worker allowance. That is a capacity allowance, not a measured worker footprint, and should be separated from actual residency when deciding whether more work fits.

These observations justify calibration and better accounting, **not dividing every forecast by two**. Whole-run maxima and phase forecasts are not synchronized ground truth; sampled RSS can miss short peaks and double-count shared pages. Different concavity, close surfaces, material properties, polynomial refinement and compression ranks can change storage and transient work substantially. Some forecast records are deliberately ceilings, while hierarchical ranks are estimates rather than hard upper bounds.

## Recommended design for the 90% target

Define the policy as permission to consume up to 90% of RAM available when the run is admitted, while continuing to account for external pressure and explicit limits. It is a ceiling, not an instruction to fill RAM unnecessarily. For example, 24 GiB available means 21.6 GiB available to new work; it does not mean 28.8 GiB merely because the computer has 32 GiB installed.

Use one request-owned memory ledger shared by nested polarizations, refinement and workers. Its conceptual admission rule should be:

1. Snapshot initial available RAM and reserve its 10% headroom once. Establish a stable run reservation, capped by explicit user and scheduler limits.
2. Keep a consistent definition of total peak, already-owned live bytes, baseline/interpreter overhead and additional allocations. Baseline memory already unavailable at the initial snapshot must not be charged again as new memory; an explicit total-process cap still includes the baseline relevant to that cap.
3. Before a phase, compute additional requirement as `max(0, predicted total live peak − matching live owned bytes)`. Include retained workers, caches and transient copies once, including overlap during replacement builds.
4. Check both the stable reservation and current physical/commit headroom. For a fixed initial physical reserve, additional allocation must fit current available RAM minus that reserve and other workers' promised-but-not-yet-allocated bytes. Record unknown estimates rather than assigning speculative residency credits.
5. Coordinate reservations centrally for concurrent jobs. Each worker must not independently claim 90% of the same free RAM. Within a scheduler, distinguish materialized memory from outstanding reservations so the same bytes are not deducted twice.
6. Reuse an admitted phase's payload allowance through assembly and factorization. Revalidate incremental needs at phase transitions rather than rebuilding a total allowance from remaining free RAM.

Keep these controls automatic. The user-facing interface needs the target/budget, estimated peak, current usage and a useful explanation on refusal; it does not need another backend picker or collection of internal memory knobs.

Implementation order: **(1)** fix budget ownership, stable storage allowance and zero/unknown detection; **(2)** introduce typed refusal reasons and RAM/commit/reservation telemetry; **(3)** separate disk payload and reload admission; **(4)** replace fixed payload shares and redundant scheduler margins with measured phase budgets; **(5)** calibrate forecasts and expand concurrency under the same ledger. A blanket switch from 60% storage to 90% storage is not recommended.

## Recovery and larger geometries

The current compressed recovery releases idle tile workers and reduces angle batches before main monostatic admission. This is useful and passed the existing tests. It cannot make an intrinsically oversized operator/inverse fit. It also does not provide general recovery for arbitrary storage-cap exceptions occurring during construction.

When a phase would exceed its reservation, prefer releasing reusable caches/idle workers, processing polarizations separately, reducing angle batch or assembly concurrency, and spilling eligible retained operators. Retry only after partial objects and traceback-held arrays have been released, with cancellation and numerical checks intact. Every retry should report its changed resource plan.

Existing tile assembly and partner spooling already process portions of the problem in chunks. The current inverse still needs its retained factor tree and construction workspaces in memory. Supporting a problem whose minimum operator-plus-factor live set exceeds the budget would require a genuine disk-backed factor strategy or a different iterative/matrix-free formulation and preconditioner. A memory-mapped file or more pagefile space alone does not establish that capability or good performance.

The representative 12-foot inlet at 15 GHz fits comfortably in the measured runs. That does not certify every 12-foot concave object, layered material, or narrower cavity. Mesh unknowns, interacting regions and actual compression ranks are the relevant capacity variables, and the user's exact geometry remains untested.

## Acceptance work before claiming reliable 90% utilization

Add regression cases for: owned memory increasing while external use stays fixed; identical phase decisions before/after own allocations; compressed partner reuse and reload; true external pressure; explicit and parent caps; zero versus unknown probes; insufficient Windows commit; transient old/new factor overlap; cancellation and cleanup after refusal; and simultaneous workers competing for one reservation. Existing accuracy gates must continue to pass.

Then perform controlled fresh-process trials at 70%, 80%, 85% and 90% of a deliberately bounded reservation, with combined process-tree sampling and memory snapshots at each allocation boundary. Include PEC, dielectric, coating, narrow inlet and refined meshes, and one/two/four-worker schedules where CPU capacity permits. Validate both successful near-limit cases and deliberate refusals; compare all retained angles and certification outcomes. Finally validate near 90% physical availability on the target 32 GiB machine with external-pressure monitoring. This audit did **not** fill the workstation to 90%, and it does not claim that boundary has been validated.

The live audit run had a 6 GiB RSS/private-commit guard, 2 GiB available-memory floor and 600-second timeout; none triggered. These were audit-run guards, not changes to solver policy. Historical input hashes and audited source hashes are saved alongside the report so later implementations can be reviewed against this evidence.
