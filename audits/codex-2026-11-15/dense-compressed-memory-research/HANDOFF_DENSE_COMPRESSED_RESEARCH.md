# Dense and Compressed memory/workflow research — Claude handoff

Parent: `27afe8f3fb523a0a61f2a99ebb77e9e2708f16d7`.
Research branch: `codex/dense-compressed-memory-research-2026-11-15`.
Production files, native binaries, solver thresholds and user options are unchanged.

## Decisions supported by this work

1. **Do not enable inverse packing by default.** At 32,768 unknowns it reduced
   retained inverse bytes by 41.9%, but whole-process peak RAM by only 7.3%
   (3.682 to 3.414 GiB). The 180-angle solve became 25.9% slower and total
   compute time 2.7% slower. This is a possible memory-pressure option; it is
   not a general speed improvement or a 42% reduction in required machine RAM.
2. **Do not promote residual row-blocking alone.** The paired physical-matrix
   microbenchmark favors the existing full product. A single whole-solve timing
   that looked favorable was not sufficient evidence. Persistent C-order
   coefficients are a separate follow-up experiment, reported below. The more
   promising Dense candidate is **F-order multiplication output for narrow
   RHS batches**, which needs no coefficient conversion or extra full matrix.
   In the 4,096-unknown, 360-angle, 16-column-batch case, total compute time
   improved 12.3% and 12.5% in two order-reversed comparisons at unchanged RAM.
   Wide-batch and thread-count results prevent a blanket default change.
3. **Keep Dense and Compressed.** Compressed completed 32,768 unknowns and 180
   monostatic angles at 3.68 GiB here. Two dense complex128 matrices alone at
   that size occupy 32 GiB. Disk residual storage can remove one resident
   coefficient copy, but it does not make the LU factor itself out-of-core.
4. **Keep batching and disk conclusions workload-specific.** We tested 180 and
   360 actual monostatic directions and both automatic/off RHS compression.
   Narrow batches can trade memory for additional products and lost RHS-basis
   reuse. The measured disk control includes real reads, but is not a desktop
   memory-pressure experiment.

## What ran and how strong the evidence is

88 fresh case processes were attempted; 88 completed.
Failed cases: `[]`. There are 84
saved-array comparisons. Their largest per-angle density relative error is
5.07366e-11, and largest peak-normalized complex-field error is 1.33949e-10.
The predeclared limits were 1e-7 and 1e-8 respectively; RHS matching uses 5e-15.

The star runs freshly assemble exact coefficient rows (64 separately seeded
random rows plus trace anchors) and check every original illumination at a
1e-12 normwise backward-error limit. These are additional sampled equations,
not a full exact matrix reference. The material runs keep production condition
and strict discrete quality gates. All four normal/transpose/adjoint cases
also compare against fresh full Dense matrices, including a lossless epsilon=12
dielectric. `analysis.json` is **array replay**, not another independent solve.

The 16,384- and 32,768-unknown packing comparisons use baseline Compressed plus
fresh exact-row checks. There is no fresh full Dense reference at those sizes
in this study. Mesh convergence, analytic scattering agreement, three-dimensional
objects, Windows DLL performance and a 32 GB desktop are **not** certified here.

Numerical jobs ran serially in fresh processes. Environment: 16 GiB cgroup,
four-CPU quota, one assembly/BLAS thread except the requested and reported
four-thread PEC20ft cases and labeled microbenchmarks. No new native compilation
was needed. `environment.json` verifies 278 unchanged production files;
`source_dependencies.json` verifies the inherited harness against the parent tree.

## Geometries and materials

All cases are **2-D P1 Galerkin** problems. Panel counts are not universally
unknown counts. The actual physical-material test dimensions are:

| Case | Size m | GHz | Panels | Unknowns | Dense condition estimate |
| --- | --- | --- | --- | --- | --- |
| pec20ft | 6.096 | 2.0 | 4096 | 4096 | 383.5 |
| coated | 0.3 | 5.0 | 652 | 1036 | 7381.5 |
| multilayer | 0.3 | 5.0 | 959 | 1669 | 31993.8 |
| partial | 0.3 | 5.0 | 504 | 742 | 1046.6 |
| cavity | 0.3 | 5.0 | 568 | 568 | 397.4 |
| dielectric_star | 0.3 | 5.0 | 512 | 1024 | 1562.9 |
| multilayer-TM | 0.3 | 5.0 | 959 | 1669 | 16781.4 |

PEC20ft is a 6.096 m (20 ft) diameter circle at 2 GHz, TE. The other physical
cases have a 0.3 m nominal outer size at 5 GHz. Coated: PEC core, radius ratio
0.7, dielectric epsilon=4-0.2i. Multilayer: outer epsilon=4-0.2i, middle radius
ratio 0.85, inner epsilon=9-0.3i, PEC core radius ratio 0.65; both TE and TM
are checked. Partial coating has bare PEC, coated PEC and dielectric junctions.
Cavity is a narrow concave PEC contour. The standalone dielectric star has
seven lobes, epsilon=4-0.2i. Relative permeability is one. Exact generated
coordinates and material tables are in the evidence `.geo` files.

The scaling star is a different, five-lobed single dielectric interface:
r(theta)=1+0.2*cos(5*theta), epsilon=3-0.08i, TE. Unknown counts
4,096/8,192/16,384/32,768 correspond to 2,048/4,096/8,192/16,384 panels and
k*nominal-radius=40/80/160/320. Its circumscribed diameter is
15.3/30.6/61.1/122.2 air wavelengths. These are electrical-scale benchmarks,
not four separate asserted meter dimensions. We have not demonstrated a
20-foot, complex multilayer object at 15–18 GHz in this study.

## Compressed inverse packing

The process-local prototype packs only completed inverse-node `v12`, `v21`,
`e1`, `e2` arrays to complex64. Leaf and Woodbury-correction LU stay complex128;
the authoritative retained operator and all acceptance gates stay unchanged.
Construction packing means parent inverses use packed children. Finite and
nonzero-to-zero checks reject unsafe casts; casting workspace is admitted.
Post-build packing is separately measured at 8,192 unknowns.

| Unknowns | Packing | Inverse MiB | Factor peak GiB | Process peak GiB | Assembly s | Factor s | Solve s | Compute s | Refinement steps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8192 | none | 142.5 | 0.547 | 0.700 | 38.41 | 3.21 | 2.86 | 44.79 | 2 |
| 8192 | construction | 90.4 | 0.522 | 0.686 | 37.01 | 3.57 | 3.93 | 44.78 | 3 |
| 16384 | none | 401.3 | 1.335 | 1.594 | 107.21 | 13.32 | 8.33 | 129.47 | 2 |
| 16384 | construction | 240.0 | 1.267 | 1.476 | 116.52 | 12.97 | 14.00 | 144.09 | 3 |
| 32768 | none | 929.6 | 3.215 | 3.682 | 401.83 | 47.38 | 32.04 | 482.86 | 3 |
| 32768 | construction | 540.2 | 3.043 | 3.414 | 403.70 | 50.70 | 40.32 | 495.96 | 5 |

These are individual scale trials, not statistical confidence intervals.
At 16,384 unknowns, assembly also varied between trials; do not attribute that
variation to inverse packing. At 32,768, assembly was essentially unchanged
(401.83 versus 403.70 s); refinement increased from three to five steps.
The operator alone retained 2,006,649,760 bytes at that size, more than twice
the baseline inverse's 974,777,536 bytes. Packing the inverse cannot remove
the operator, assembly workspace, or angle-sweep buffers.

The 8,192-unknown controls were repeated in reverse order. Stage and final
high-water RSS include the validation harness; final RSS may also include
archive work. Batch RSS is captured before saving that batch. Retained bytes,
construction accounting, sampled RSS, and process high-water RSS are different
metrics and are preserved separately.

## Dense residual products and persistent coefficient layout

Physical 8,192-square matrix; four alternating-order repeats per configuration.
Median product seconds, with existing F-order coefficients:

| Threads | RHS columns | Full | Rows256 | Rows256 + C copy |
| --- | --- | --- | --- | --- |
| 1 | 16 | 0.4520 | 0.4574 | 1.6822 |
| 1 | 180 | 1.3883 | 1.5065 | 2.6716 |
| 4 | 16 | 0.1743 | 0.1948 | 1.5396 |
| 4 | 180 | 0.6169 | 0.7112 | 2.0789 |

The exploratory layout prototype keeps one persistent C-order original matrix
and reuses the owned F-order assembly buffer for in-place LU. This still has
two dense matrices; it is not a quadratic-memory reduction. It requires an
owned writable F-order input and explicit RAM residual storage. Matrix-copy
admission uses the production lock/check. It preserves physical coefficients,
condition scaling, residual checks and restoration of the shared assembly buffer.

Paired persistent-layout product medians (both layouts resident in this
microbenchmark, so these timings are not a memory-capacity demonstration):

| Threads | RHS columns | F full | C full | C rows64 |
| --- | --- | --- | --- | --- |
| 1 | 16 | 0.4799 | 0.2668 | 0.2808 |
| 1 | 180 | 1.5389 | 1.3652 | 1.7084 |
| 4 | 16 | 0.2039 | 0.1207 | 0.1508 |
| 4 | 180 | 0.8145 | 0.7112 | 1.1249 |

Full 8,192-unknown / 180-angle Dense trial measurements:

| Case | Solve s | Compute s | Peak GiB |
| --- | --- | --- | --- |
| star-8192-180-dense-full | 7.122 | 57.228 | 2.247 |
| repeat-star-8192-180-dense-full | 6.173 | 54.031 | 2.258 |
| star-8192-180-dense-blocked | 5.617 | 56.362 | 2.258 |
| repeat-star-8192-180-dense-blocked | 6.447 | 61.348 | 2.256 |
| star-8192-180-dense-blocked_c | 8.615 | 54.274 | 2.280 |
| layout-star-8192-180-full | 5.367 | 54.691 | 2.248 |
| layout-star-8192-180-blocked | 6.328 | 58.154 | 2.248 |

The layout check validates physical coefficients and bitwise restoration,
normal/transpose/adjoint solves, a zero RHS column, and LU buffer aliasing.
Production dual-polarization checks additionally recorded:

| Case | Assembled-system reuses | Prototype restore calls | Discrete gate passed |
| --- | --- | --- | --- |
| pecsmall | 1 | 0 | True |
| multilayer | 1 | 0 | True |
| dielectric | 1 | 1 | True |

The PEC/multilayer cases reused assembled data but did not restore the same
coefficient buffer. The added dielectric lifecycle case explicitly exercises
that restoration path; the nonzero call counter is required by this report.

These are research prototypes, not complete production integrations. Any
promotion needs a repeatable end-to-end benefit on target BLAS/hardware and
tests for cancellation, allocation failure, concurrent admissions, unowned
inputs and fallback/disk policies. Material-run timing includes full-density
serialization inside the solve recorder; use those runs for accuracy/lifecycle
checks rather than a clean performance ranking.

### Follow-up: change product output layout without copying coefficients

The C-order result motivated a further exploratory check, not part of the
initial plan: `X.T @ A.T` transposed back, or `matmul(A, X, out=F_output)`.
Both keep the original coefficient matrix. Paired product medians:

| Threads | RHS columns | F full | C full | Transpose formulation | F output |
| --- | --- | --- | --- | --- | --- |
| 1 | 16 | 0.4780 | 0.2612 | 0.2230 | 0.2260 |
| 1 | 180 | 1.6496 | 1.2977 | 1.4114 | 1.3296 |
| 4 | 16 | 0.2304 | 0.1164 | 0.1082 | 0.1116 |
| 4 | 180 | 0.6910 | 0.6663 | 0.7219 | 0.7371 |

The F-output prototype allocates only the usual product-sized result; it adds
no n-by-n matrix and no coefficient conversion. It preserves residual checks.
The small-batch products improve substantially here, but the 180-column,
four-thread case does not. Do not turn that into a universal output-layout rule.
Full-solve controls (RHS compression off for the 360-angle comparison):

| Case | Solve s | Compute s | Peak GiB |
| --- | --- | --- | --- |
| star-8192-180-dense-full | 7.122 | 57.228 | 2.247 |
| output-star-8192-180-full | 5.540 | 54.192 | 2.248 |
| star-4096-360-dense-off-batch16 | 7.654 | 19.526 | 0.608 |
| output-star-4096-360-batch16 | 5.263 | 17.123 | 0.609 |
| repeat-control-star-4096-360-batch16 | 8.686 | 22.255 | 0.608 |
| repeat-output-star-4096-360-batch16 | 6.643 | 19.468 | 0.608 |
| star-4096-360-dense-off-batch256 | 2.887 | 14.868 | 0.691 |
| output-star-4096-360-batch256 | 2.817 | 14.469 | 0.684 |

The narrow-batch pair was repeated in reverse order. These full-solve trials
and a production dual-polarization dielectric case
are included in the array comparisons. A narrow-batch output policy is a
better follow-up candidate than copying the whole coefficient matrix, but
needs paired repeated whole-solve trials on other BLAS/thread configurations
before production promotion. Its result must be separated from the slower
row-blocking prototype and the persistent C-matrix prototype.

## 360-angle batching

Angles 0 through 359 degrees, same geometry and one factor per process.
The label `off` means RHS compression is disabled; otherwise it is automatic.
All original columns are validated, even if fewer basis columns are solved.

| Configuration | Solved RHS columns | Solve s | Compute s | Peak GiB |
| --- | --- | --- | --- | --- |
| dense-full-batch256 | 360 | 3.308 | 15.195 | 0.691 |
| dense-blocked-batch256 | 360 | 2.978 | 14.671 | 0.691 |
| dense-full-batch16 | 360 | 9.375 | 26.714 | 0.608 |
| compressed-none-batch256 | 360 | 2.417 | 18.042 | 0.388 |
| compressed-construction-batch256 | 360 | 3.233 | 18.465 | 0.370 |
| compressed-none-batch16 | 360 | 2.956 | 20.628 | 0.283 |
| compressed-construction-batch16 | 360 | 3.923 | 19.438 | 0.266 |
| dense-off-batch256 | 360 | 2.887 | 14.868 | 0.691 |
| dense-off-batch16 | 360 | 7.654 | 19.526 | 0.608 |
| compressed-off-batch256 | 360 | 2.314 | 17.758 | 0.388 |
| compressed-off-batch16 | 360 | 3.198 | 18.239 | 0.283 |

The 180-angle cases cover -90 through 89 degrees. Neither sweep duplicates
its endpoint. Keep full-angle work, batch width, automatic RHS compression,
and refinement counts separate when explaining speed differences.
None of these 360-angle controls reduced the number of solved RHS columns;
lost basis reuse is a possible batching interaction, not the measured cause
of the slowdown in this particular suite.
Even with F-order output, the 16-column Dense batches remained slower overall
than the wide-batch control. This improves a RAM-saving configuration; it does
not justify shrinking batches when the wide sweep already fits comfortably.

## Disk control

`disk-residual-benchmark.json` uses the production ResidualSpool for a 1 GiB
physical matrix. Creation plus fsync took 2.13 s. With one thread, cached /
advised-evicted / cached-again product times were 0.298 / 0.430 / 0.294 s for
16 RHS and 1.452 / 1.455 / 1.462 s for 180 RHS. `/proc/self/io` recorded
1,073,741,824 read bytes for each advised-evicted product and zero for cached
controls. File-cache advice is local to our temporary file. The original
matrix remained resident; no global cache was dropped and no 32 GB pressure
or out-of-core LU was simulated. NVMe/Windows results may differ substantially.

## Evidence correction and reproduction

The original material recorder hooked the base CompressedFactor.solve, but
HMatrixFactor overrides it. Original fields, quality gates and measurements
are preserved; those runs did not capture Compressed densities. The corrected
runner explicitly hooks HMatrixFactor and repeats all 21 cases under `capture-`
labels. It changes no numerical solver. See `CAPTURE_NOTE.md`.

Read `README_REPRO.md` for commands. `evidence/MANIFEST.json` indexes split
lossless evidence; `unpack_evidence.py` verifies archive and per-array hashes.
All full RHS, density, complex-field and exact-row residual arrays are retained,
along with original result JSON, stdout/stderr, geometry and return codes.
Original NPZ hashes identify source containers; restored numerical values and
C/F layouts are checked bitwise by `verify_evidence.py`. Regenerated ZIP bytes
need not match. Replayed analysis must match the original analysis as well.

## Independent review requested from Claude

**First state your own hypotheses and acceptance criteria, then perform fresh
checks independently, and only then cross-analyze our evidence.** Label each
finding as fresh solve, fresh equation evaluation, saved-array replay, source
inspection, or another model's measurement. Agreement between models is not
an additional numerical validation.

1. Reproduce the memory/speed tradeoff using independent peak measurements and
   a larger, more difficult geometry. Does construction packing make an
   otherwise rejected memory-capped solve finish, with all original gates?
   Check near-limit admission, rebuilds, and retained-array byte accounting.
2. Stress packing on high-contrast, low-loss/resonant multilayers and junctions,
   both polarizations and adjoint condition probes. Use fresh Dense anchors
   where feasible and new independently seeded exact rows elsewhere. The
   current large-scale evidence is one dielectric star family.
3. Prioritize the no-coefficient-copy Dense output-layout candidate, especially
   narrow batches. Independently assess the persistent C-order layout too. Does it improve
   actual 180/360-angle runs on another BLAS/thread configuration after counting
   copy/restoration costs? Verify shared-polarization lifecycle, cancellation,
   failures and admission before proposing production code. Reject it if the
   gain is marginal or unstable.
4. Cross-check batching with automatic RHS compression both on and off. Can a
   memory-aware batch policy save useful RAM without losing more in repeated
   operator work or RHS-basis reuse? Preserve original-angle validation.
5. For larger Compressed wins, profile the retained operator and its assembly
   rather than assuming inverse storage dominates. Investigate reusable/nested
   far-field bases or bounded temporary assembly only with measured rank,
   accuracy and total-memory accounting; no savings are established for these
   proposals here. For Dense, test real local-storage pressure before extending
   disk policy. Fully out-of-core LU would be a separate, much larger project.

FMM was not rerun in this handoff. Continue its independent review separately;
these Dense/Compressed results neither validate nor invalidate an FMM speedup.
Do not merge a research hook or change a user-facing default on the strength of
retained-byte counts or a single favorable timing.
