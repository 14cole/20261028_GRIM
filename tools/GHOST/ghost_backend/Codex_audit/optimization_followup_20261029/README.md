# Solver optimization follow-up

The preceding completed implementation was pushed to `origin/main` as `6c73ccd`. That push contains code, tests, reports and compact summaries; raw experimental archives remain locally available. The changes described below were made afterward.

## Measured bottleneck and implementation

The initial 12-foot by 3-foot inlet profile at 15 GHz spent 3.507 seconds in 766 detailed worker-memory snapshots. Parent-process memory readings took only 0.031 seconds. Times are inclusive; nested measurements must not be added. This identifies the worker working-set query as the main remaining admission-query cost, not a reason to remove allocation checks.

`WorkerPool.incremental_memory_snapshot()` now uses fresh RSS and private-commit readings for incremental allocation admission. On Windows these are available without the expensive USS working-set walk. RSS includes shared pages, so it is used only as a conservative charge against the existing reservation. It grants **no worker residency credit**. Whole-footprint and phase admission retain the detailed unique-residency probe. Platforms without private commit in the cheap reading retain the full probe. No new cache, stale-worker allowance, forecast discount, RAM cap or user option is introduced.

`MemoryBudget.require_reload()` selects this incremental path. Its physical and commit headroom still come from live OS readings; pending holds, overlapping-request accounting and explicit/scheduler limits remain. Small construction groups retain the previously bounded observation policy. A missing worker reading prevents observation reuse. Metadata identifies whether a check used incremental charges or unique-residency credit.

Before refusing because the conservative worker RSS charge exceeds the reservation, the final implementation retries once with a detailed unique-residency reading and fresh OS limits. It still rejects when that exact check does not fit. This avoids introducing a false low-memory refusal from shared RSS pages. The fast successful path is unchanged. Two boundary tests cover acceptance after refinement and genuine rejection, including exactly one detailed retry.

## Junction projection finding and fix

Combined regional potentials route a slave junction endpoint to its master for D/W densities while retaining independent S/K' endpoint densities. The ordinary polynomial interpolation does not commute with that routing: `R3 P != P R2`. The saved pre-fix map gives a nonzero commutator norm of 0.496904 for both TE and TM in the partial-coating fixture. The previous matrix discrepancies therefore were not roundoff or a tolerance issue.

`polynomial_pair.prolongation()` now rejects this incompatible layout, and the existing preparation path records the reason and falls back to independent assembly. The shared preparation guard protects dense and compressed optional reuse. Default assembly and junction physics are unchanged. The test retains independent numerical comparisons for supported layouts and verifies exact independent matrices for the declined junction layout; no numerical tolerance was relaxed. The optional reuse mode remains off by default.

`junction_reason.py` and `junction_reason.json` preserve the algebraic reproduction against the pre-fix source. `before/` stores the changed production baselines. `source_hashes.json` identifies the implementation used for the trials.

## Validation artifacts

The first focused run passed 113 tests and 27 subtests, including live worker charging, fresh large-allocation checks, pressure refusal, missing samples, request accounting, worker lifecycle, polynomial pairs and junction physics. A final run and the following studies are recorded alongside this report:

- `comparison_plan.json` and `comparison_finish_plan.json`: repeated before/after inlet solves with query profiling. Before arms load the saved pre-change memory-budget and worker-pool modules in an isolated child process.
- `qualification_plan.json`: a moderate-dielectric dogleg, a coated inlet, a lossy magnetic dogleg at 15 GHz, and a conducting inlet with a 2 GiB solve cap. All use the representative 12-foot geometry. These are capacity/behavior observations, not a universal material qualification.
- `concurrency.py`: two actual certified solves in one process, compared with serial references. It verifies independent reservations, no reused construction observations during overlap, field agreement and reservation cleanup.

The first after-arm launcher failed before any solve because of an audit-script import error. It was fixed, its raw failure record retained, and that arm is excluded from timing statistics. Neither solver output nor numerical tolerances were changed to obtain a passing result.

The monitor's 14 GiB process-tree guard and 2 GiB host reserve bound these experiments only; they are not new solver limits. The source-encoding failure documented in the preceding audit remains outside this optimization's scope.

## Results

### Inlet timing and accuracy

| Mean over two runs per arm | Pushed implementation | Faster live worker charges |
|---|---:|---:|
| Certified solve | 120.308 s | 117.108 s |
| Factorization | 20.269 s | 17.955 s |
| Worker memory-query time | 3.489 s | 0.219 s |

The improvement is **3.199 seconds / 2.66%** of solve time, with about **93.7% less worker-query time**. All four runs certified on the same 14,295-node mesh and produced bit-for-bit identical VV and HH fields. Sampled private-memory peaks were 2.656-2.683 GiB before and 2.694-2.701 GiB after: there is no demonstrated total RAM reduction. Full worker snapshots fell from hundreds per solve to 16; 749 cheap live snapshots supplied the remaining worker checks.

The control is the pushed implementation, which already included bounded construction observations. These runs do not independently establish the total overhead versus the older solver with no construction safeguards, nor prove the earlier proposed 2% overhead target. The new worker-query cost itself is now under 0.2% of this solve's time.

The repeated comparison and material trials preceded the final exact-on-refusal boundary refinement. Their frozen hashes are in `timing_source_hashes.json`. A final confirmation on the completed code took **117.243 seconds** and again certified with identical fields. `source_hashes.json` identifies that final code. This distinction is intentional; earlier timing data have not been relabeled as measurements of a later file revision.

### Material and tight-cap qualification

| Case, all 12 ft by 3 ft and 15 GHz | Solve cap | Outcome |
|---|---:|---|
| Moderate-dielectric dogleg, epsilon 4-0.04j, mu 1 | 12 GiB | Certified in 366.133 s; peak private memory 6.830 GiB; fields identical to the earlier reference |
| Conducting inlet with representative 1/8-inch dielectric coating | 12 GiB | Trial timer stopped it at 240 s; peak private memory about 4.20 GiB; no certified result |
| Lossy magnetic dogleg, epsilon 101.19-11.88j, mu 3.45-3.47j | 12 GiB | Planning rejected large refinement forecasts, then reached the configured panel limit; no matrix solve qualified |
| Conducting inlet with deliberately tight cap | 2 GiB | Trial timer stopped it at 180 s; peak private memory about 1.87 GiB; no certified result |

The magnetic diagnostics retain earlier planned systems of 160,068 and 320,104 unknowns, with modeled requirements of about 420 and 838 GiB. These are conservative forecasts, **not measured peaks**; they cannot establish the actual minimum RAM. The final panel-limit error also does not mean the machine ran out of memory. The coated and tight-cap runs were stopped by experimental timers, not by an OS memory kill or a newly imposed solver time limit.

These results support the tested conducting and moderate-dielectric cases. They do not qualify arbitrary coatings or bulk magnetic geometries under the user's 32 GiB maximum. Existing disk/chunk processing does not by itself remove the number of unknowns demanded by internal wavelength and refinement, or guarantee convergence. Relaxing numerical gates or increasing forecasts without evidence would not establish accuracy.

### Concurrent solves

Three completed trials each ran a 3 GHz conducting inlet and a 1 GHz moderate-dielectric dogleg, first serially and then concurrently in the same process. Both used the 12-foot geometry, 13 angles, two assembly threads, one BLAS thread and a 4 GiB reservation per solve. Mean combined wall time fell from **15.810 to 11.971 seconds**, a **24.3% reduction**. Individual solves can take longer while sharing the CPU; the improvement is in completing both jobs.

All six parallel results certified and agreed with serial references within 4.28e-15 relative error. Requests were correctly marked as overlapping, held separate 4 GiB reservations, reused no construction observations during overlap, and released all reservations afterward. This is a useful two-request qualification, not evidence of unlimited concurrency or externally saturated host memory.

The original harness intermittently received Windows `PermissionError` while creating parallel output folders, preventing one request from reaching its start barrier. A repeated attempt captured both that error and the resulting barrier timeout. Precreating all output folders serially fixed the harness, after which all three trials passed. No solver synchronization rule was changed. An initial verification script also assumed exact bitwise concurrent fields; it now checks the study's original 1e-10 comparison threshold, reporting the actual approximately 1e-15 differences. No solver accuracy threshold was changed.

### Final checks

The final regression run passed **184 tests and 27 subtests in 38.09 seconds**. It includes exact field comparisons for dense/compressed junction fallback at degrees two and three, independent junction physics tests, allocation/ownership/refusal checks, worker lifecycle, and compressed workspace/recovery coverage. The final inlet and concurrent confirmation artifacts validate the final boundary-refinement revision. The earlier full suite was not rerun in this follow-up; the known ASCII-source check remains unresolved.

`summary.json` and `verify_results.py` verify the saved outputs, timing arithmetic and final source hashes. Failed and timed-out attempts are preserved and excluded from successful timing averages.

## Recommendations after this work

Keep these changes. The remaining worker-query cost is small enough that further tuning has diminishing value. Keep compressed as default, dense and impedance as manual overrides, polynomial reuse off by default, and forecast discounts disabled.

Prioritize the coated model's iteration/rank and conditioning behavior, and the magnetic model's discretization/forecast scaling. Separate studies should determine whether a validated approximation or a different large-system numerical method is needed. Do not promise that chunking alone makes every 12-foot material geometry fit or certify. The moderate-dielectric success and the concurrent results are concrete qualifications of their tested cases.
