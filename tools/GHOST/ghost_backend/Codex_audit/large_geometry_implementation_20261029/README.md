# Large-geometry implementation for Claude review

Implemented October 28, 2026 Arizona time / October 29 UTC. This package follows the [large-geometry audit](../large_geometry_ram_speed_audit.md) and [comparison with Claude](../large_geometry_comparison_with_claude.md).

The implementation delivers the four priority-one resource/speed changes and the idle-worker release option from priority two. It preserves the existing operator, physical residual, sample-row, condition and mesh-convergence acceptance limits. Dense remains available. No blanket reduction of RAM forecasts or unconditional change to inverse accuracy is introduced.

## Changes

| Change | Behavior and review points |
| --- | --- |
| Correction-memory accounting | Both compressed phase forecasts explicitly include restarted GMRES basis, work vectors and small correction arrays. The width is `min(angle_batch_size, 16)` and the restart length is 20. This allowance is added to ordinary RHS work. Models are versioned `compressed_phase_v2` and `compressed_hmatrix_v2`. See [memory.py](../../compressed/memory.py). |
| Full admission after hierarchical rejection | Before tile construction, rank/error/storage fallback resamples the actual oracle and prices tile workers, assembly, inverse, RHS, correction and retained resources. Live residency in excess of the structural allowance is also charged. It can release idle workers; otherwise it refuses before tile construction. Failed hierarchical arrays are released before admission. See [runtime.py](../../compressed/runtime.py). |
| Smaller angle batches | When neither Automatic candidate fits, the planner releases idle workers and halves the requested batch down to one as needed. It keeps all requested angles, reuses the factor across batches and reruns the existing admissions. Cached forecasts are repriced; a multi-frequency call uses a common batch before ranking combined peaks. Request and adaptive-step execution use the selected batch and record it. See [selection.py](../../execution/selection.py), [options.py](../../execution/options.py) and [adaptivity.py](../../twod/adaptivity.py). |
| Optional stronger inverse | If three refinements have not converged, attempt one upgrade from the ordinary 1e-8 inverse approximation to 1e-10. Require replacement payload room and live construction headroom of at least `max(64 MiB, 3 * old_inverse_bytes)`. Keep the old inverse until the replacement succeeds and deduct its bytes from the replacement's payload allowance. A storage/rank/numerical failure restores it; cancellation propagates. Refinement restarts against the same operator and RHS. See [factor.py](../../compressed/factor.py). |
| Release idle workers | Owned worker pools track whether a tile traversal is active. Resource recovery may close an idle team and remove its retained reservation; it cannot close an active traversal. Later work creates a new team normally. See [worker_pool.py](../../compressed/worker_pool.py) and [tile_processes.py](../../compressed/tile_processes.py). |
| Accurate fallback context | CPU state and assembly sessions retain the angle count and current formulation resource record, so fallback admission uses the actual job. See [cpu.py](../../execution/cpu.py) and [session.py](../../twod/assembly/session.py). |

Automatic batch reduction belongs to request/adaptive-mesh planning. Explicit modes keep the requested angle batch. The separate HPC scheduling cost model is unchanged; execution still applies its per-worker memory reservation and actual-mesh admission. This patch does not claim a new batch-throughput optimizer.

## Measured result

Synthetic 12 ft by 3 ft reentrant contour, 4 ft-deep by 1 ft-wide notch, filled with the audit's high-contrast lossy magnetic material; 1 GHz, 361 angles, both polarizations, four threads, double precision, adaptive P2/P3 certification. This is a homogeneous TYPE 3 body, not a coated PEC inlet or a finite 3D aircraft. The final systems have 12,972 unknowns per polarization.

| Run | Full certified solve | Peak process-tree RSS | Final GMRES columns | Maximum solved RHS batch |
| --- | ---: | ---: | ---: | ---: |
| Matched upgrade-disabled control | 57.12 s | 1.486 GiB | 301 | 256 |
| Automatic upgrade, 8 GiB budget | 44.60 s | 1.508 GiB | 0 | 256 |
| Automatic mode, 3.1 GiB budget | 43.79 s | 1.329 GiB | 0 | 128 |

The serial matched pair improved time by **21.9%**, with **22.3 MiB more peak RSS**. The reduced-batch run saved **182.4 MiB** relative to the upgraded 256-column run. All three runs passed the unchanged quality and mesh-convergence gates and returned all 361 angles in each polarization. Maximum normalized field differences were 9.59e-12 for the upgrade and 5.64e-16 for batch reduction. The prior fixed-1e-10 audit experiment was faster still because it did not pay for building and replacing an initial inverse; it was not used to claim the production gain.

These are single matched runs, not a broad speed guarantee. Two earlier diagnostic upgrade runs (44.0 and 47.9 seconds) are retained, but excluded from the matched comparison because validation activity overlapped the diagnostic period. RSS is sampled every 100 ms and differs from private commit; both are saved. The 3.1 GiB value is the requested admission budget, not the measured consumption or a hard operating-system cap.

In a separate real two-worker lifecycle check, release removed **148.8 MiB of child RSS** and a **960 MiB forecast reservation**. Closing took 0.006 seconds; restarting and evaluating a near-quadrature tile took 0.94 seconds. Tile coefficients were identical. A forecast reservation is deliberately larger than these small workers' measured residency; do not report the whole reservation as measured RAM saved.

See [measurements.json](measurements.json), [worker_release.json](worker_release.json), and the `benchmarks/` request/result/metadata/monitor/field files. Reproduce with [capacity_probe.py](capacity_probe.py), [summarize.py](summarize.py) and [worker_release_probe.py](worker_release_probe.py). The control disables only the optional upgrade in the benchmark process.

## Validation and failure recovery

**202 unique tests passed** across the focused and broader regression runs. [validation_summary.json](validation_summary.json) deduplicates the latest result for every test; individual timestamped reports preserve failed attempts and their subsequent resolution. Subtests are not counted again in the unique total. The [validation harness](validate.py) records every result, disables unrelated pytest plugins, uses workspace-local temporary files and sets UTF-8 child output on Windows.

Coverage includes measured GMRES allocations at batch sizes 1, 8, 16, 64 and 256; refused/failed/canceled upgrades; batch exhaustion and common-frequency repricing; released failed assembly arrays; rank, sampled-error and storage fallback before worker construction; worker loss/cancellation/restart; forward/transpose/adjoint products; and numerical comparisons across PEC, impedance, dielectric, lossy magnetic, layered, multiple-body, thin-gap, acute and reentrant examples. The 10,000-panel capacity regression, headless worker settings and the shared BoR compressed path are also checked.

Two existing tests intentionally corrupt the preconditioner to exercise GMRES. They now deny replacement construction space so the new successful upgrade does not bypass their intended path. Their original accuracy and GMRES assertions remain. Earlier headless failures were temporary-directory rename permissions and Windows log encoding; rerunning with the harness environment resolved them without changing the production worker code.

## Boundaries and remaining recommendations

This is the measured near-term implementation, not completion of the research roadmap:

- Inactive H-matrix partner spill, reciprocal H-matrix query reuse and P2/P3 hierarchical reuse remain unimplemented. They need ownership, memory, formulation-sign and independent-error qualification. The existing worker near-integral reuse is retained.
- No blanket rank/phase forecast calibration is applied. Existing conservative allowances are retained, and the new GMRES component can increase forecasts. Refinement can still increase the final system far beyond the initial candidate.
- A small-preconditioner iterative capacity backend, active matrix/factor block storage, FMM/directional methods and distributed single-matrix solves remain separate development work. Angle batching cannot make an oversized operator or inverse fit. HPC still distributes independent jobs.
- The upgrade trigger is a refinement-count heuristic, not a proved optimal timing decision. It can cost an extra factor build on a problem that would eventually converge cheaply. Its construction allowance is also a conservative heuristic, not a bound on every transient allocation. Payload caps and final numerical checks remain enforced.
- The fallback sampler is bounded and checkpointed; admission remains a forecast. A new rank or storage failure after admission can still reject the solve. Sparse narrow gaps, resonant cavities and different materials need their own acceptance cases.

Claude's proposed cavity condition-gate override, universal forecast discount and fixed 6,000-unknown dense/HODLR crossover are not adopted; the reasons in the audit comparison still apply. Existing bounded dense leaves are retained. No new public factorization mode is added.

## Review package

[implementation.patch](implementation.patch) is a standalone unified diff. [changed_files.json](changed_files.json) records before/after SHA-256 values. `before/` and `after/` hold source snapshots, and [capture.py](capture.py) verifies the baseline and creates the package. The implementation is in the working tree; this package does not assert a new commit or push.

Review admission before allocation, optional-upgrade rollback and cancellation, batch propagation through cached and adaptive plans, and the distinction between measured residency and reserved memory. The larger capacity recommendations above remain explicitly open.
