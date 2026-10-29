# Memory accounting implementation — 29 October 2026

The reviewed false-refusal mechanisms are addressed by request-owned accounting, stable automatic storage allowances and admission checks before later phases and disk reloads. The local 2D driver now allows 90% of available RAM instead of also imposing a 75%-of-installed ceiling. Compressed remains the default; no automatic dense/compressed picker was reintroduced.

This delivery also includes the previously reviewed, uncommitted compressed-default, batch-recovery and diagnostic-export changes. Their reports remain in the adjacent audit folders.

## Implemented behavior

- `execution/memory_budget.py` establishes a request-local allowance from initial physical availability, Windows commitment headroom and any explicit/scheduler cap. Automatic payload allowance derives from this stable reservation, not the free RAM left after assembly. Later parent caps can tighten it. The 16 MiB payload floor cannot exceed the enclosing reservation.
- Operators and factors are weakly registered, so accounting does not retain completed arrays. Later gates credit tracked allocations, bounded by the process's observed RSS/private-commit growth since entry. Unrelated process growth alone receives no credit. Existing explicit resident hints retain their established caller contract; they are combined by maximum, not added to tracked credit.
- Worker pools provide complete/incomplete samples of their own processes. Residency credit uses unique resident pages where available, avoiding summed shared-page credit. Private commitment is tracked separately. Current samples are saved for calibration; the conservative allowance for future worker buffers and caches remains in forecasts.
- Concurrent request reservations within a process deduct other requests' outstanding allocations while preserving the largest active initial physical reserve. Nested solves inherit the same ledger. Spawned frequency workers remain subject to the parent scheduler's assigned reservations. This is not a new machine-wide coordinator for independently launched applications.
- Current physical availability and commitment headroom are checked at admission and before compressed factorization/solving. Exceptions identify the binding constraint and required/admitted quantities. Unknown availability is represented by `None`; a successful zero reading can no longer silently restore an explicit RAM cap. The local scheduling helper no longer raises a small/zero budget to 1 GiB.
- Compressed operators now expose resident bytes separately from logical payload bytes. Paired tile assembly and inverse partner reservations exclude finalized disk payload. Reload checks the retained-storage cap and incremental restoration headroom, including a temporary workspace allowance; pressure/cancellation/corruption cleanup retains the existing ownership and checksum behavior. Polynomial retained-operator spools similarly update resident accounting and check reload capacity.
- Batch recovery still preserves every requested angle. Independent frequencies in a direct multi-frequency request can start from the requested batch again, while refinement and polarizations within each frequency share reductions.
- Saved result metadata includes `memory_accounting`: initial availability, baseline RSS, the most recent constraint, bounded phase checks and worker measurements. The outer public result stores at most 64 checks and 16 worker samples, with a count of omitted earlier checks, avoiding duplicate histories in nested results. It is request-local; no past-solve cache or persistent learned preference is added.

## Validation

**467 unique test/phase results pass** in the final aggregate. The main affected suite passed 257 tests and 74 subtests; the remaining GUI/driver/default/certification suite passed 208 tests and 5 subtests; the spawned-driver test passed separately. The final bounded-telemetry check passed 43 tests and 30 subtests. Overlapping checks are deduplicated by test ID in [validation_summary.json](validation_summary.json).

New regressions cover the original 24 GiB / 10 GiB operator false refusal for both factor constructors, external pressure, unowned allocations, resident-credit bounds, weak ownership, explicit/parent caps, zero versus unknown detection, Windows commit exhaustion, phase rechecks, simultaneous reservations, worker uniqueness, spool refusal cleanup, frequency batch reset and controlled 70/80/85/90% admission boundaries.

The following fresh-process trials used the representative 12-foot geometry, 15 GHz, all 361 angles and current public compressed default:

| Case | RAM reservation | Automatic payload allowance | Peak tree RAM | Peak private commit | Solve time |
|---|---:|---:|---:|---:|---:|
| Ordinary PEC inlet | 6 GiB | 3.6 GiB | 2.270 GiB | 2.834 GiB | 124.02 s |
| Narrow PEC inlet | 6 GiB | 3.6 GiB | 2.581 GiB | 3.145 GiB | 138.64 s |
| Moderate dielectric inlet | 8 GiB | 4.8 GiB | 3.986 GiB | 4.355 GiB | 162.90 s |

All three passed the original numerical and mesh-certification checks. Every complex output sample matched its saved compressed reference exactly. The payload allowance stayed constant over all 37, 37 and 24 reads respectively. The audit guards (6 GiB tree RSS/private, 2 GiB available-memory floor, 600 seconds) did not trigger. Times are validation observations, not a controlled performance comparison; other regression work ran on the host during portions of validation.

The final metadata-only adjustment limits saved telemetry to the outer result and 64/16 records. It was checked afterward with the request-budget, public compressed-recovery and execution-option tests, including small real numerical solves. The three raw large-run exports above preserve the earlier, more verbose telemetry; their numerical algorithms and admission behavior are unchanged by that export-size adjustment.

All **85 historical input files** used by the memory audit remain unchanged. The old audits' source hashes intentionally describe the pre-fix code; their source-hash verifiers should not be treated as current-source tests. [source_hashes.json](source_hashes.json) identifies the implementation validated here. `summarize.py` verifies final test outcomes, trial results, stable allowances and preserved historical inputs.

An existing worker-crash/pipe-cleanup test stalled under restricted process access. Its isolated rerun with normal Windows process access passed, as did the broad rerun. A separate spawned-driver test initially lacked the package import path; the audit harness now propagates `PYTHONPATH`, and that test passed on rerun. Those failures and the corrected runs remain in the saved reports; no numerical gates were loosened to make tests pass.

## Deliberately retained limits and follow-up studies

The 60% automatic retained-payload share and existing forecast growth allowances remain. The review found overlapping reported components, not evidence that all safety margins could be removed. Baseline and worker telemetry now support subsequent component-level calibration; current RSS is not substituted for future construction/cache capacity. The HPC 85% allocation policy and desktop automatic frequency-worker count are unchanged.

Registered ownership is intentionally conservative: it does not credit every Python cache or unrelated allocation in a shared process. RSS sampling is not an exact attribution system; physical credit is bounded rather than inferred from all process growth. Forecasts remain estimates, and external processes can change memory pressure between checkpoints. These checks do not turn the numerical solver into an operating-system-enforced RAM quota.

The 90% policy and controlled admission boundaries are implemented and tested, but these trials did **not** fill the workstation to 90% of physical availability. A dedicated near-capacity study on the target 32 GiB machine, synchronized phase/component profiling, wider material/coating coverage, and aggregate concurrent-worker trials remain validation/calibration studies. No general disk-backed inverse or matrix-free replacement was added. The implementation therefore does not claim every complex 12-foot geometry fits.
