# Memory accounting follow-ups — 29 October 2026

Implemented the three corrections recommended in [the review of Claude's audit](../claude_implementation_review_20261029/README.md): shared-process reservation accounting, incremental reload/phase checks, and workspace-based automatic storage. The compressed default and manual dense override remain in place. There are no new user controls or persistent records of past solves.

## What changed

### Shared-process reservations

Overlapping requests now join a synchronized reservation group at scope entry, before their first forecast. Its aggregate capacity is fixed from the initial physical/commit allowance. New reservations subtract other requests' complete reservations; already allocated pages do not create new capacity. Completion and cancellation release the reservation. Nested calls inherit their existing request.

Once requests overlap, their parent-process growth cannot be attributed exclusively. Parent RSS/private-growth and baseline credits are therefore withheld for those requests for the rest of their lifetime. Separately owned worker processes can still receive measured unique-resident/private credit. Admission never samples another request's workers or mutates its telemetry.

This deliberately favors reliable accounting over maximizing same-process concurrency. It is not a new concurrent-solver scheduling policy. The existing BLAS lock can serialize numerical phases even while public requests overlap. Separately scheduled processes retain their existing parent reservations and worker limits.

The previous counterexample admitted 30.6 GiB of reservations against a 21.6 GiB target. The regression now admits 12 + 9.6 + 0 GiB. Additional tests cover real threaded admission, cancellation, request entry before pricing, and overlapping public solves with unchanged certified fields.

### Incremental allocation checks

Spool reloads check the **additional payload plus reload workspace** against current physical headroom and current commit headroom independently. Their total request-owned usage is checked separately against the stable reservation. Existing GUI/process baseline is not treated as a new allocation. Numeric ownership, observed request growth and owned workers are retained in the total check; forecast overhead remains conservative.

Phase forecasts credit only the explicitly modeled process baseline, bounded by its measured entry residency/commit. Geometry, caches and future workspaces do not receive blanket baseline credit. A phase also prices observed numeric payload when it exceeds the original estimate. Explicit caps, scheduler reservations, per-tile reload checks, spool cleanup and cancellation remain enforced.

Both false-refusal reproductions now pass. Separate tests still reject physical pressure, commit pressure and total-cap overruns. Error diagnostics now identify why the stable reservation was limited, including initial commit headroom, and label reload quantities as additional allocations.

### Workspace-based storage

For automatic storage, each mesh receives:

`payload allowance = max(0, stable reservation − largest phase non-storage allowance)`

The three phase allowances cover assembly, factor construction and solving. They include interpreter/geometry allowances, retained workers and polynomial partners, construction growth beyond the retained inverse, RHS/GMRES work and projection caches. These are alternative phase envelopes, not a sum of mutually exclusive workspaces. Existing optional factor-replacement overlap checks remain enforced.

The 60% policy is only a fallback when no usable phase forecast exists. It is not a floor: 10 GiB total with 6 GiB workspace grants 4 GiB payload. Explicit payload settings retain their existing meaning; the hierarchical legacy 2048 MiB setting retains its automatic interpretation without a 2 GiB floor overriding a smaller allowance.

Hierarchical forecasts use the supplied allowance and reserve paired assembly workspace so enabling a second operator cannot invalidate the sizing calculation. Scheduler estimates use the same policy. Main monostatic, bistatic, boundary-density and thin-layer admissions activate the actual mesh plan. Speculative backend/polynomial estimates cannot replace it; analytic-zero admissions clear an earlier plan. Tile fallback installs its own conservative phase envelope.

An allowance can change for a new mesh or a tighter parent cap. Allocating an operator alone no longer shrinks it. Storage-heavy phases can receive more than 60%; workspace-heavy phases can receive less. Worker-growth allowances have not been reduced without calibration.

## Validation

[Machine-readable summary](validation_summary.json), [test runner](validate.py), [trial runner](trace_solve.py), [pressure-ramp runner](physical_pressure.py), and [source hashes](source_hashes.json) are saved here. The summary contains **391 unique latest test/phase results, all passing**, including 24 new parameterized regression results. Broader suites cover worker crashes, spool recovery, memory detection, scheduling, compressed defaults, materials/thin layers, projection, factor workspaces and BoR behavior. Subtest results are retained in the raw reports; overlapping runs are not added together as independent tests.

Four new certified trials use representative 12 ft × 3 ft 2D inlet shapes at 15 GHz, all 361 requested angles, four assembly/BLAS threads, and the public compressed default. Every trial passed numerical and mesh certification and reproduced both saved polarization fields exactly.

| Trial | Reservation, GiB | Observed peak tree RSS, GiB | Peak private commit, GiB | Payload allowance across meshes, GiB | Elapsed, s |
|---|---:|---:|---:|---:|---:|
| Ordinary inlet | 6.0 | 2.282 | 2.843 | 2.855–5.349 | 155.8 |
| Narrow inlet | 6.0 | 2.612 | 3.170 | 2.763–5.347 | 173.4 |
| Moderate dielectric inlet | 8.0 | 3.990 | 4.356 | 5.246–6.040 | 192.0 |
| Ordinary inlet, tighter cap | 4.6 | 2.269 | 2.834 | 1.455–3.949 | 151.5 |

The tighter trial's largest forecast is 4.549 GiB against 4.6 GiB allowed. This is a near-forecast-cap test, not 90% physical-RAM utilization. On the largest ordinary-inlet mesh, the non-storage allowance is 3.145 GiB. That leaves 2.855 GiB payload under a 6 GiB reservation, or 1.455 GiB under 4.6 GiB.

RSS is sampled for the process tree and can double-count shared pages. Private commit is a different quantity. Some regression work overlapped these numerical trials; the timings are not controlled speed comparisons. Large trials preceded the final diagnostic wording, measured-worker reload accounting and stale analytic-zero plan cleanup; focused regressions cover those final changes. No numerical kernels or quality thresholds changed.

All 85 historical evidence files checked by the prior hash manifest are unchanged. New raw evidence lives in this folder. Early failed test runs are preserved, including a test helper argument error and an integration-test barrier incorrectly placed inside the existing BLAS lock; the latest corrected outcomes pass. One nonexistent test filename collected nothing and was corrected.

## What the real-memory ramp found

Two short supervised subprocess trials allocated and touched real memory without mocking platform probes. Both released their allocations on exit. An external monitor enforced an available-RAM reserve and a timeout.

The first reached **79.90% of initially available physical RAM** before a reservation guard stopped further allocation. The second recorded approximately **16.67 GiB available RAM** but only **14.59 GiB available commit**. Therefore the stable allowance was **13.13 GiB**, set by 90% of commit headroom, rather than the 15.00 GiB physical-RAM allowance. It touched **13.07 GiB** of payload, about **99.5% of that binding reservation**, with room for allocator metadata. A further 0.125 GiB request was correctly rejected with `initial_commit_headroom` identified in the message.

The later ramp's requested 80%, 85% and 90% physical targets were all clamped to that same commit-based ceiling. They are not three distinct increasing physical-utilization achievements. Its observed numeric fraction was 78.41% of initial available RAM. The earlier ramp's smaller bookkeeping allowance caused its guard stop; the follow-up used 64 MiB for allocator metadata and completed normally. The second ramp briefly overlapped the small public-request integration test; live probes and the supervisor remained active.

**A real 90%-of-available-physical-RAM solve has not been demonstrated.** On this host during these trials, commit capacity was the tighter constraint. The experiment confirms that substantial free RAM can coexist with a valid allocation refusal. No pagefile or operating-system setting was changed to force the test through.

## Remaining studies

The implementation fixes the demonstrated accounting defects and provides mesh-specific capacity allocation. It does not guarantee that arbitrary 12 ft inlet geometries or materials will fit, nor that every valid solve will achieve 90% physical utilization.

The next useful study is a complete numerical solve near 90% available RAM on a host with sufficient commit headroom, followed by matched isolated/concurrent throughput measurements. Worker component measurements should precede any reduction in their conservative future-growth allowances. Same-process credit attribution remains deliberately conservative; increasing concurrency should use separately measured worker ownership rather than restoring ambiguous RSS credits.

Changes are local and ready for review. This request did not commit or push them.
