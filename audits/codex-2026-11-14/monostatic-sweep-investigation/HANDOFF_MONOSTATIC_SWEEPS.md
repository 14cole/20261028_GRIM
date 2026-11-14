# Monostatic sweep investigation and handoff to Claude

## Decision

The user's normal workload is **180–360 monostatic incidences**, not many receive
directions for a single illumination. That makes reuse of an already built factor
central to backend selection. The measured Dense/Compressed baselines remain much
faster than the research FMM on the small and medium full sweeps tested here.
The fastest tested 8,192-unknown FMM variant was `star-8192-180-fmm-block_gmres-tol0.0001`: 873.4 s at 0.432 GiB. It remained 19.7× slower than Compressed on this case.

Against baseline FMM, the strongest full-sweep trial reduced measured compute
by 43.1% with
6.5% higher peak RSS.
The additional matched 24-angle residual-check probe reduced timed Krylov work
from 110.3 to 70.3 seconds
(36.3%); that improvement still needs a
full-sweep validation. These are measured cases, not universal speedup factors.

Keep the current production backends and user-facing options. This branch adds
research, validation and evidence only. No production module, GUI control, shipped
DLL or shipped SO changed. FMM remains a candidate for memory-constrained cases;
these results do not establish the 32k/65k many-angle crossover.

I agree with Claude's correction of its earlier per-angle Compressed timing and
its many-angle interpretation. This study extends that work with actual 180/360
angle sweeps, corner/thin-slot cases, reuse controls, block solvers, inverse
storage, and Dense disk/batch controls. It is not a rerun of Claude's 32k 16-angle
or 65k two-angle measurements.

- Parent: `codex/fmm-matched-ablation-review-2026-11-14`, `0b0c50808d94ba8b3316cb1e70816a61312d1014`.
- Reviewed Claude context: `5275e7f1f213e9f6d122062b9de9b985883024e6`,
  `audits/claude-2026-11-15/fmm-many-angle-review/REVIEW_AND_MANY_ANGLE_MEASUREMENT.md`.
- New branch: `codex/monostatic-sweep-investigation-2026-11-14`.

## What was measured

58 fresh-process cases completed; 11,424
physical incident columns were solved across them. The suite includes full
180/360-angle sweeps, four-angle smoke checks, one 24-angle warm-start probe and two
24-angle stronger-preconditioner controls.
All cases ran serially with one assembly/BLAS thread in a 16 GiB Linux container,
not on the user's 32 GB desktop. See `environment.json` for exact versions and
the hashes of 278 unchanged production files.

The systems are **2D P1, single-interface dielectric** models with epsilon
3−0.08i: a five-lobed star, a square, and a U-shaped body with a 0.02-wide slot in
a body of width 2. The slot has sharp corners and nonuniform panel lengths.
TE is the main study; the slot also has separate TM runs. This is not a layered
PEC/dielectric or BoR validation. Unknowns equal twice the panel count for these
specific closed P1 dielectric systems.

For each fixed geometry/frequency/polarization, setup and factorization are paid
once. Only the RHS, solve and matched receive projection vary with incidence.
GHOST's incidence angle points toward the source: monostatic projection uses the
**same angle**, as production does. `check_projection.py` verifies matched
projection against the diagonal of the full bistatic grid for arbitrary complex
densities. It also checks the RHS's 360-degree periodicity numerically.

The grids are half-open: [-90,90) at one degree has 180 incidences; [0,360) at one
degree has 360. A separate 180-angle full-circle grid uses two-degree spacing.
Both endpoints included would add a sample; 0 and 360 are the same physical
incidence. No interpolation or symmetry shortcut is used.

Compute time below is setup + RHS + solve + matched projection. Extra audit row
validation and array serialization are excluded from compute, but included in
whole-process wall/RSS records. Exact validation rows remain resident during
solving. These are factor-harness measurements, not GUI, mesh-certification,
frequency-sweep, or export timings. Dense references use double precision and
in-memory original coefficients unless explicitly labeled disk.

## Baselines: setup is amortized over the whole sweep

| Case | Setup s | Solve s | Compute s | Peak GiB |
|---|---:|---:|---:|---:|
| `star-2048-180-dense-cold` | 3.66 | 0.46 | 4.17 | 0.224 |
| `star-2048-180-compressed-cold` | 5.05 | 0.45 | 5.56 | 0.168 |
| `star-2048-180-fmm-cold` | 25.85 | 201.79 | 227.70 | 0.157 |
| `star-2048-360-dense-cold` | 4.10 | 1.14 | 5.37 | 0.224 |
| `star-2048-360-compressed-cold` | 5.50 | 0.91 | 6.53 | 0.168 |
| `star-2048-360-fmm-cold` | 28.53 | 518.83 | 547.50 | 0.157 |
| `star-8192-180-dense` | 45.21 | 5.39 | 50.83 | 2.248 |
| `star-8192-180-compressed` | 41.25 | 2.94 | 44.43 | 0.702 |
| `star-8192-180-fmm` | 78.84 | 1455.78 | 1534.94 | 0.406 |

These are single samples. Small time differences are not established speedups;
host variability was visible even between identically configured setup phases.
Retained array bytes, process peak RSS, work counts and wall time are different
quantities. Complete measurements and every comparison are in `RESULT_TABLES.md`
and `analysis.json`; raw per-case records are under `results/`.

## FMM improvements: measured limits and remaining opportunity

| Case | Setup s | Solve s | Compute s | Peak GiB |
|---|---:|---:|---:|---:|
| `star-8192-180-fmm` | 78.84 | 1455.78 | 1534.94 | 0.406 |
| `star-8192-180-fmm-recycle` | 80.50 | 1381.11 | 1461.92 | 0.405 |
| `star-8192-180-fmm-rhs_qr` | 83.91 | 1378.12 | 1462.26 | 0.425 |
| `star-8192-180-fmm-batch8` | 83.38 | 1823.73 | 1907.37 | 0.528 |
| `star-8192-180-TE-fmm-block8` | 85.02 | 1360.11 | 1445.45 | 0.415 |
| `star-8192-180-fmm-cold-tol0.001` | 84.07 | 1256.82 | 1341.22 | 0.412 |
| `star-8192-180-fmm-block_gmres-tol0.001` | 86.94 | 1016.58 | 1103.78 | 0.422 |
| `star-8192-180-fmm-block_gmres-tol0.0001` | 87.33 | 785.88 | 873.44 | 0.432 |

The baseline uses accurate double-precision FMM, a complex64 construction
operator for the approximate preconditioner, and a double inverse. It releases
the construction operator after checking unchanged normal/transpose/adjoint
inverse actions. Default preconditioner operator/inverse tolerances are 0.01;
the stronger trials change both to 0.001 or 0.0001. **Accurate FMM and the final
original-RHS residual requirements never change.** A loose preconditioner is
not accepted as a production-accurate operator.

- **Previous-angle initial guesses:** the larger 24-angle probe needed the same
  1,312 accurate operator applications as the matching first 24 cold angles,
  and essentially the same solve time (~197 s). This is a measured probe, not
  an extrapolated full 180-angle warm result. Small full sweeps also showed
  essentially unchanged work.
- **Recycling:** LGMRES retained eight augmentation vectors plus the previous
  solution. Inner-30 cold/recycled controls and separate inner-80 controls are
  included. At 2k/180, inner-80 recycling used 6,380 A applications versus 6,524
  for cold LGMRES and 6,366 for ordinary GMRES. There is no useful demonstrated
  win over GMRES here. The 8k LGMRES result changes both solver and reuse policy;
  do not attribute its small timing difference solely to recycling. This does
  not rule out larger or different recycled/deflated subspaces.
- **Incident basis:** the 2k half-circle FMM trial solved 79 basis vectors for
  180 illuminations, but 8k needed 169. Reconstruction checks every original
  incident RHS with accurate FMM. The 360-angle 2k trial used ranks 107 and 50
  in its two batches; this research FMM path does not carry a shared basis
  across those batches. Basis indices in its JSON `angles` list are work
  counters; physical angles are in the saved arrays and spec.
- **Batched independent GMRES:** width 8 shares matrix applications but keeps
  separate Krylov spaces. It helped the smaller model, but the larger trial
  used two cycles (one restart), 88 inner steps per batch, 18,180 RHS-equivalent
  accurate A applications, and more RAM. This is not a universal batching win.
  Its outer angle batch was 64, versus 256 in the large scalar/block controls;
  account for that configuration difference when comparing RSS.
- **Shared block GMRES:** this is a different, rank-aware shared search space.
  Width 8 retains at most 168 basis columns per restart, versus 648 vectors
  for eight independent restart-80 solves. It helped the small/slot cases more
  than the large weak-preconditioner case. The full-sweep trials check true residuals
  after every block step, adding many accurate FMM applications. A separate
  24-angle probe below checks every fourth step and at restart/breakdown. This conservative
  checking policy is a concrete optimization target, not evidence that block
  Krylov methods have no further value.
- **Stronger preconditioners:** compare both setup and solve in the table;
  tolerance changes only the preconditioner. The 0.001 scalar/block pair provides
  a matched full-sweep method control. The scalar 0.0001 control covers 24
  matched angles, not a full 180-angle sweep.

## Focused 24-angle follow-ups

All three rows use the same -90 through -67 degree incidences, 8,192 unknowns,
and 0.0001 operator/inverse preconditioner tolerances. Times isolate the timed
Krylov solves; the first row is the saved first 24 angles of the completed full
sweep, not an extrapolation. Each fresh probe also paid its own setup cost,
recorded in the complete tables. The 24-angle probes retain smaller RHS/solution
arrays than the full 180-angle control; lower probe RSS is not evidence of a
cadence-related RAM reduction.

| Matched 24-angle control | Timed Krylov solve s | Accurate A RHS-equivalents |
|---|---:|---:|
| Shared block, check every step (first 24 of full sweep) | 110.253 | 1152 |
| star-8192-24-fmm-block-cadence4-tol0.0001-probe | 70.277 | 768 |
| star-8192-24-fmm-cold-tol0.0001-probe | 125.091 | 813 |

The four-step cadence still checks the true original residual at restart and
breakdown, and every accepted original RHS must meet the unchanged 1e-12 limit.
`check_block_cadence.py` validates both cadences against a direct solve, including
duplicate, zero and all-zero RHS. This probe tests whether checking overhead is
worth addressing; it is **not a measured full-sweep speedup** and has not been
promoted to production. The scalar probe supplies the missing matched-strength
method control over these 24 angles. Full-sweep extension remains for Claude.

## Angular redundancy depends on electrical size

The following are **RHS-only rank scans**, not large-system solves. They use
production row-max scaling and a 2e-15 relative Frobenius threshold. FMM basis
trials use a different equilibration. Numerical rank depends on scaling,
discretization and the threshold; do not equate these rank counts exactly.

| Unknowns | k | 180 over half-circle | 180 over full circle | 360 over full circle |
|---:|---:|---:|---:|---:|
| 2048 | 20 | 85 | 119 | 154 |
| 8192 | 80 | 170 | 180 | 338 |
| 32768 | 320 | 180 | 180 | 360 |
| 65536 | 640 | 180 | 180 | 360 |
| 32768 | 20 | 68 | 105 | 106 |

At the larger electrical sizes, the tested angular sets are full rank. Refining
the mesh at fixed k=20 remains compressible, so panel count alone is not the
explanation. With radius bounded by 1.2, a one-degree incidence change produces
up to ~0.42 radians of phase change at k=20, ~1.68 at k=80, and ~13.4 at k=640.
Numerically adjacent angles need not give similar incident vectors on a large
electrical body. Full RHS rank does not rule out better preconditioning or a
reusable spectral subspace; it limits near-exact reconstruction from fewer
incident vectors at this threshold. Production's bounded batching and shared incident-basis path
already exploit useful redundancy; they are not missing features to re-add.

The Dense full-circle star also disproves generic 180-degree mirroring:
opposite-direction power differs by up to 0.620 of sweep peak power. Reciprocity
alone does not supply the missing half-circle. Use verified geometry/material
symmetry before eliminating requested incidences.

## Existing production batching and incident-basis reuse

| Case | Setup s | Solve s | Compute s | Peak GiB |
|---|---:|---:|---:|---:|
| `star-2048-360-dense-batch16` | 3.58 | 1.33 | 5.10 | 0.224 |
| `star-2048-360-dense-batch256` | 3.55 | 0.76 | 4.42 | 0.256 |
| `star-2048-360-compressed-batch16` | 5.23 | 1.22 | 6.64 | 0.168 |
| `star-2048-360-compressed-batch256` | 5.09 | 0.80 | 6.04 | 0.201 |

The Compressed batch-256 run solved 160 columns for 360 physical incidences,
using its existing shared-basis path; batch 16 solved all 360. Wider batches
used more RAM. Dense's auto policy can prefer direct LU solves when QR would
not pay. These measurements validate existing mechanisms, not a missing new
feature. They do not justify forcing a large batch regardless of RAM headroom.

## Dense disk storage and batching

| Case | Setup s | Solve s | Compute s | Peak GiB |
|---|---:|---:|---:|---:|
| `star-8192-180-dense` | 45.21 | 5.39 | 50.83 | 2.248 |
| `star-8192-180-dense-memory-batch16` | 44.44 | 16.57 | 61.41 | 2.129 |
| `star-8192-180-dense-disk-batch256` | 45.34 | 5.44 | 50.99 | 1.259 |
| `star-8192-180-dense-disk-batch16` | 46.17 | 13.04 | 59.60 | 1.130 |

These exercise an **existing** production feature. The 8k original matrix is
1 GiB. Disk mode retains LU in RAM and streams the original matrix for full
residual checks; it is not an out-of-core LU factorization. The in-memory and
disk batch-16 controls separate batching from storage choice.

| Disk batch limit | Logical read GiB | Storage read GiB | Write accounting GiB | Cancelled writes after cleanup GiB |
|---:|---:|---:|---:|---:|
| 256 | 2.003 | 0.000 | 1.042 | 1.000 |
| 16 | 24.003 | 0.000 | 1.042 | 0.992 |

Both disk trials report about 1 GiB of cancelled writes and negligible storage reads. These were predominantly page-cache runs: the lower process RSS must not be described as an equal reduction in total machine RAM, or as a measurement of SSD spilling under pressure.

In this single sample, in-memory batch-16 solving was slower than the warm-cache
disk batch-16 path, despite the extra logical reads. This is not evidence that
SSD storage is faster: host variation and the row-blocked versus whole-matrix
residual products are possible explanations. A paired repeat/profile should
separate them before changing either implementation.

The I/O columns are Linux `/proc/self/io` accounting, including cleanup where
available. Fresh processes do not imply a cold filesystem cache, and buffered
write accounting does not prove completed media writes. These are not SSD
throughput or memory-pressure eviction benchmarks. RSS excludes reclaimable
filesystem page cache, so it is not total system RAM consumption. Keep the
existing memory-aware storage/batch policy; these tests do not justify forcing
disk storage for every solve or adding a new UX control.

## Compressed inverse storage

Post-construction complex64 off-diagonal storage saved 52.07 MiB
(36.5% of inverse-only retained bytes) on the 8k Compressed
case. Leaves stayed double. Reachable arrays including its retained operator
fell from 462,387,368 to 407,783,592 bytes. Peak RSS did not improve because the
construction peak had already occurred. Solve refinement increased from two to
three steps. The extra setup/probe work and host variation make total wall-time
comparison insufficient to establish a speed benefit.

Normal/transpose/adjoint random inverse actions changed by approximately 4e-7;
the physical forward solves passed their original equations and Dense array
comparisons after refinement. Those random action probes are not a full adjoint
equation validation suite. The small FMM packing trial saved only 1.40 MiB.
This is a targeted retained-storage candidate, not a demonstrated peak-RAM fix.
Production admission/accounting, construction-time packing, difficult materials,
and fallback behavior need review before integration.

## Validation and evidence

All 50 full-array comparisons passed. Maximum
peak-normalized complex-field difference was 3.448e-12;
maximum per-angle density relative L2 difference was 3.479e-09.
Acceptance limits were 1e-8 and 1e-7 respectively. Every batch also passed fresh
exact-coefficient rowwise backward checks below 1e-12 (64 seeded random rows plus
vertex/trace positions). FMM checked every original RHS's accurate scaled relative
residual at <=1.1e-12; the custom batched/block routines use <=1e-12.
Field dB comparisons exclude reference amplitudes below 1e-3 of peak, avoiding
misleading pointwise percentages at deep nulls. These checks validate agreement
for the same discrete mesh, not mesh convergence or conditioning certification.

Four harness issues were caught and repaired:

1. A broad batch-file glob could swallow a named `-batch8` control. Numeric final
   suffix matching in `evidence_paths.py` and preference for an exact consolidated
   case filename prevent this in both original and restored evidence. The strict
   replay caught a restored `fmm-batch8` control being selected for its shorter
   baseline label. Every original case's file count and every restored case's
   array bytes were checked. No solve or archived value changed.
2. Different RHS batch widths differed at roundoff scale. A generation-only
   rerun reproduced saved bit patterns on this host. The comparator now records
   bitwise identity and requires RHS agreement within 5e-15 in peak and per-angle
   L2 metrics. Maximum observed per-angle RHS difference was
   7.289e-17. No solver gate changed. The initial failure is
   retained in `analysis-failed-rhs-bitwise.stdout`.
3. The shared-block unit test found tiny SVD-induced values for an exactly zero
   RHS. Its exact zero solution is now preserved before the true residual check.
   Duplicate, zero and all-zero tests pass against a direct solve. The initial
   failed test is retained in `block-check-failed-zero-rhs.stdout`. This fix
   preceded all physical shared-block sweeps.
4. All restored array values were bit-identical, but C versus Fortran storage
   changed the last few bits of some norm reductions. The analyzer now loads
   both originals and restored arrays in canonical C order. The complete
   analyses were rerun and match exactly; no acceptance limit changed.
   `analysis-replay-difference.json` and `archive-analysis-replay-failure.stdout`
   preserve the initial differences and failure, including the case-selection
   issue described above.

The lossless evidence archive contains full complex densities, original RHS,
matched fields, angle grids, exact-row residuals/norms, and complete solver/timing
records and stdout/stderr. It consolidates batches, not original NPZ ZIP bytes.
All 406 restored arrays were compared bit for bit with
their original batch values; replaying the analysis on the restored evidence
produced an identical result. `ARRAYS_MANIFEST.json` checks each part and the
archive; the inner index checks every reconstructed array/record/log.
Archive SHA256: `9a10b0d5334414360f3164dfa5b1d66d37eec2fb78d4012dbd99c24a165da4f1`.

See `README_REPRO.md` for build, restore, quick checks and full rerun commands.
The research paired-panel SO was reused from the prior audited source and its
build script is included. It is separate from shipped production libraries.
Full suites take hours; inspecting/restoring evidence does not require rerunning
every solve. Failed checker evidence was retained rather than silently discarded.

## Questions and next investigations for Claude

1. Independently replay all arrays, then repeat the most promising stronger
   preconditioner case and its Compressed control in interleaved fresh processes.
   Separate repeatable changes in work from host timing variation. Extend the
   24-angle scalar 0.0001 control to a full sweep before attributing the full
   0.0001 result to block solving.
2. Review and extend the measured four-step residual-check cadence probe to full
   sweeps. Investigate a projected-residual trigger and reliable early residual
   replacement in the block/batched prototypes. Preserve the
   final original-RHS gate. Instrument projected and true residual histories to
   explain the extra restarts; test widths 4/8/16 and restart capacity before a
   full sweep. Do not accept projected convergence alone.
3. Run selected full 180/360-angle Compressed/FMM cases at 32,768 and 65,536
   unknowns. Prior few-angle setup advantages make this the unresolved crossover.
   Use full arrays and additional exact rows; the rank scans here are not those
   solves. Include real thread counts and a measured 32 GB machine/memory budget.
4. Investigate sharing S/K-prime's plain-source far translation. Code inspection
   shows eight translation passes per dielectric apply with active far plans
   (six exterior, two interior, including three for weak Maue W); this sharing could remove two.
   This is a pass-count opportunity, **not a 25% runtime forecast**. Near work and
   other costs remain. Preserve Maue W and the near/far partition; do not replace
   it with a strong derivative without the necessary corrections.
5. For inverse packing, measure construction peak and current residency, not
   just retained bytes. Validate normal/transpose/adjoint equations, refinement
   and fallback on high-contrast, low-loss and poorly conditioned cases. Check
   scheduler/admission accounting before any production use. Also test disk
   residuals under actual memory pressure/cold I/O; cached file reads do not
   establish large-desktop performance. Profile the small-batch RAM/disk
   discrepancy and test blocked in-memory residual products as a separate
   Dense performance hypothesis.
6. Extend full sweeps to larger corner/thin-gap bodies, multiple interfaces and
   PEC/dielectric layers, with mesh and conditioning certification separately.
   Current full solves reach 8,192 unknowns and at most ~30.6 wavelengths across
   the bounding diameter. The 65k RHS scan reaches ~244.5 wavelengths but is not
   a solution at that scale. No universal panel/angle backend threshold or
   guarantee for a 20-foot, 15–18 GHz desktop model follows from this study.

The investigation still covers Dense, Compressed and FMM. The practical priority
is retaining efficient factor reuse and bounded memory in the production paths,
while testing whether the specific FMM opportunities above can improve its
memory-versus-time tradeoff enough to justify integration.
