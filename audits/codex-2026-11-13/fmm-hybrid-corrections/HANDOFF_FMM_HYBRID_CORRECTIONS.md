# FMM hybrid corrections, integrated panel moments and actual compressed preconditioning

Reviewed Claude commit `597b591a60db239ac82b758b55e8f6116e095792`, starting with
`audits/claude-2026-11-13/fmm-hybrid-review/REVIEW_AND_ASSIGNED_TESTS.md`.
Parent Codex research commit: `bfc524037a16065c55bbeb6fcb71fe7bd316f776`.

**The straight-side bug is confirmed and corrected in research code.** In the
8,192-unknown control, FMM peaks at 0.44 GiB versus
2.12 GiB for Dense and 0.55 GiB for existing
Compressed. Its setup, factorization and two solves take about
413 seconds,
and independent exact-row validation/evidence work brings the worker total to
434 seconds. Dense/Compressed worker totals are about
249/267 seconds. This is
a further RAM tradeoff, not a reason
to replace the existing backends. Panel
moments and compressed near storage now work together. An actual global
compressed inverse successfully preconditions the FMM at 8,192 unknowns, and
its construction operator can be released afterward. However, the diagonal
far expansion has a further measured accuracy limitation, and the end-to-end
controls below are essential before interpreting the RAM gains as a speed win.

All 526 production files remain identical to the parent distribution. No GUI
option, backend selection, release tolerance, DLL or shared library changes.
This is a research branch, not a distribution candidate or mesh certificate.
Use this new audit directory for the corrected prototype; earlier audit snapshots
are preserved as historical evidence and still reproduce the original failure.

## Review findings and corrections

1. **Confirmed severe straight-side defect.** On the same 1,400-panel square,
   the original nodal hybrid gives relative Frobenius errors S=0.177669 and
   W=0.057528. It accepts 32 bad blocks out of 92 compressed blocks. K is zero
   on each of those blocks. Subnormal complex division contaminates the shared
   skeleton and all three ranks become zero. The corrected result has zero
   bad blocks; S=2.19e-14 and W=5.11e-14. K remains about 1.34e-13.
2. **Stronger repair than a shared scale floor.** `safe_cross.py` normalizes
   each component before the shared-skeleton routine, using a stable norm and
   separate real/imaginary scaling. A zero sampled component stays in subsequent
   row/column checks; it is never assumed identically zero or dropped. Nonzero
   subnormal samples reject to exact storage because rescaling may lose the
   requested relative accuracy. Invalid
   arithmetic/nonfinite output rejects to exact local storage. Independent
   synthetic checks preserve rank-three components scaled by 1e-300, and handle
   all-zero blocks. Claude's trial floor also reweights small nonzero components;
   this repair preserves their separate relative stopping scales.
3. **Production exposure is narrower than the research defect.** Production
   `_assemble` passes tolerances derived from a nonzero global system norm,
   rejecting vanishing sampled system rows. It does not use my per-component
   1e-300 block floor. A direct test with a zero component and ordinary global
   tolerances passes. The raw reusable routine can still fail on pathological
   subnormal tolerances; a separate fail-closed API hardening review is warranted.
   This is not evidence that the production Compressed backend has the square bug.
4. **Panel moments independently reproduced and integrated.** The adapter keeps
   two endpoint source moments, two target moments and a real normal projection,
   instead of three complex tables at eight points per panel. Phase-table storage
   is 5.33 times smaller. `build_point_phases=False` also avoids constructing and
   discarding the temporary one-point tables. All-near cases allocate no endpoint
   moment tables; small tree/translation metadata still exists.
5. **Preconditioner evidence strengthened, with an important qualification.**
   Claude's experiment factors a dense copy of a rank-truncated matrix. Its size
   is operator storage, not actual factor or construction memory. Its cutoff is
   relative to the global spectral norm of the equilibrated system, not each
   block's norm; computing that norm is outside the reported setup interval.
   It is a useful iteration experiment, not an end-to-end solver benchmark.
   Our actual HMatrix/HODLR preconditioner uses different stopping rules, so equal
   numeric tolerance values are not equivalent algorithms.
6. **A remaining far-field accuracy limitation is now measured.** The mixed
   straight/curved stadium has worst K/K′ entries above 1e-12 with separation 2.
   Increasing expansion order is not a reliable repair. See the isolation below.

## Complete operator checks

All rows below use P1, eight-point panel quadrature, compression target 1e-13,
full matrices for all four operators, and shuffled node/element ordering.
Errors are maximum absolute matrix discrepancy divided by maximum absolute
reference entry. The reference is GHOST's independent dense operator assembly.

| Case | Near panel pairs compressed | S | K | K′ | W |
|---|---|---|---|---|---|
| matrix-square-1400 | 50.9% | 2.1e-13 | 5.82e-13 | 5.82e-13 | 3.84e-13 |
| matrix-stadium-1536 | 30.6% | 9.72e-14 | 1.26e-11 | 1.27e-11 | 2.27e-13 |
| matrix-stadium-sep3 | 43.2% | 7.66e-15 | 9.52e-13 | 9.5e-13 | 8.58e-15 |
| matrix-concentric-1600 | 37.0% | 1.54e-14 | 8.5e-15 | 8.49e-15 | 1.52e-14 |

The concentric pair has radii 1 and 0.999 and k=40−0.8i. This tests genuine
compression on close contours, but **is not a complete coated-body transmission
solve**. Square uses real k=40; stadium uses k=40−0.8i. Exact-near compression
has no zero-block regression on either straight-sided case.

The compression policy remains a sampled stopping test, not a deterministic
bound on every coefficient. Nonfinite rejection fixes the silent arithmetic
failure; it does not turn randomized probes into a proof of accuracy. The
half-dimension skeleton cap and exact local fallback remain. The concentric
case has 120 cap rejections, costing storage rather than accuracy.

## Far-field stability investigation

The stadium's worst separation-2 K entry has absolute error 2.52e-16, against
an entry of magnitude 4.25e-9. The maximum-entry-normalized matrix error is
1.26e-11. Independently integrating its four supporting panel pairs agrees
with the dense reference to 1.93e-22, isolating the discrepancy from ordinary
panel quadrature. K′ gives the corresponding conclusion.

Replacing only the far contribution while retaining the same near matrix gives:

| Expansion digits | K maximum-entry error | K Frobenius error |
|---|---:|---:|
| 10 | 1.26e-11 | 1.32e-13 |
| 12 | 8.98e-12 | 9.42e-13 |
| 14 | 1.89e-11 | 1.68e-12 |

This nonmonotonic behavior is consistent with cancellation/roundoff in the
diagonal expansion; it is not fixed by asking for more terms. Separation 3
reduces the full K/K′ maximum-entry errors to about 9.5e-13 and the S/W errors
below 9e-15, but the K margin is narrow. The wider exact-near region is an
experimental accuracy control, not a new universal default or error certificate.

The pinned native FMM2D library was also run on the eight columns containing
the largest stadium discrepancies. With eps=1e-14, the worst selected-column
K/K′ discrepancies are 8.58e-15/9.56e-15; the targeted entry absolute errors
are 3.72e-20/1.39e-20. At eps=1e-12 they are about 7.75e-13 by the selected-
column matrix metric. This is a native control on selected columns, not a full
native stadium matrix qualification. The reusable diagonal adapter is much
faster per product; stable reusable wideband translations remain worthwhile.

## Fresh operator performance measurements

Single thread; separate process per row; two warmups and seven timed single-RHS
products. Numbers are medians. Peak RSS is measured before dense reference
construction. Reachable numeric storage includes unique NumPy backing buffers,
sparse buffers and geometry, excluding Python/native allocator overhead.

| Panels | Mode | Setup s | Numeric MiB | Peak GiB | S/K/K′/W ms |
|---|---|---|---|---|---|
| 2048 | stream | 53.8 | 129.89 | 0.249 | 9.56/12.63/15.11/39.76 |
| 2048 | moment_stream | 53.8 | 79.02 | 0.177 | 4.60/5.24/5.46/16.03 |
| 2048 | moment_hybrid_nodal | 120.0 | 41.17 | 0.120 | 7.81/8.69/8.22/19.00 |
| 4096 | moment_hybrid_nodal | 310.5 | 94.98 | 0.179 | 13.61/16.25/15.61/34.63 |

At 2,048 panels, moment-only storage is 39.2% lower than the point/stream
baseline, and the combined moment/nodal operator is 68.3% lower. Its measured
peak is 51.8% lower. Near compression adds construction work and
Python block-application overhead; the moment/stream row can be the better speed
choice when RAM permits. Performance rows use 16 exact reference rows and two
full random-vector products; they are not full 4,096-panel matrix tests.
The 512-panel all-near control has zero endpoint phase bytes and agrees with
the streamed reference. These fixed-k refinement tests do not prove behavior
at growing electrical size and fixed points per wavelength.

## Actual global compressed inverse with an FMM outer solve

`preconditioned_solve.py` builds the existing geometry-based HMatrix operator and
HODLR inverse at loose tolerances, applies it in GMRES to the accurate moment-
hybrid operator, and checks exact coefficient rows independently. No global
dense matrix is live during construction, solves or the recorded capacity peak.
Small dense references are built afterward; the 8,192-unknown reference is a
separate process. All runs below use restart 80, outer rtol=1e-12, two incident
angles and epsilon=3−0.08i. Field errors compare all 180 directions and both angles.

| Unknowns, k, pol. | Operator/inverse tol. | Iterations | Inverse MiB | FMM MiB | Pre-validation peak GiB | Field error vs Dense |
|---|---|---|---|---|---|---|
| 1024, 40, TE | 0.001 | 23/21 | 6.09 | 12.82 | 0.115 | 2.87e-14 |
| 2048, 80, TE | 0.01 | 26/27 | 14.04 | 24.68 | 0.146 | 3.46e-14 |
| 2048, 80, TM | 0.001 | 21/21 | 15.63 | 24.68 | 0.148 | 2.56e-14 |
| 8192, 80, TE | 0.01 | 46/48 | 62.30 | 140.39 | 0.349 | 1.23e-14 |

The deliberately loose operator is **not a released physical operator**. A
research subclass records the production release rejection and allows it only
for preconditioning with a separate accurate outer operator. Production gates
are unchanged. The actual inverse costs more iterations than Claude's exact
dense factor of the truncated matrix, which is expected rather than a contradiction.

At 8,192 unknowns, inverse construction retains 263.77 MiB of reachable
numeric data including the assembly operator. Detaching that operator leaves
62.27 MiB. Weak-reference/GC checks confirm it is released;
two-column forward, transpose and adjoint inverse actions are bit-identical
before and after release. No production HMatrix ownership or acceptance changes.
The factor must remain tied to its fixed coefficients; it cannot subsequently
rebuild itself through the discarded operator.

Exact sampled-row errors at this size are below 7e-17 in the rowwise normwise
metric ||r_i||/(||A_i||_1 ||x||_infinity+|b_i|). This is not a componentwise
backward-error formula or a full-row certificate. Earlier pilot JSONs used a
misleading `componentwise` key; the finalized records label this metric rowwise.

## Same-mesh complete-solve controls: 8,192 unknowns, k=80, TE

| Method | Assembly/setup s | Factor s | Two RHS solve s | Stage sum s | Worker total s | Dominant retained MiB | Peak GiB |
|---|---|---|---|---|---|---|---|
| Dense LU | 223.8 | 23.4 | 0.95 | 248.1 | 248.7 | 2048.0 | 2.124 |
| Existing Compressed | 262.8 | 3.6 | 0.25 | 266.7 | 267.2 | 440.0 | 0.546 |
| FMM + loose global inverse | 396.5 | 1.4 | 14.66 | 412.6 | 433.9 | 202.7 | 0.435 |

For FMM, setup includes both the loose preconditioner operator and the two media's
FMM operators. For Dense/Compressed, these are existing production factor classes,
with their residual checks. Neither side runs mesh/condition certification.
Field projection/reference analysis is outside the three timed stages. The
worker-total column includes the FMM exact-row checks and evidence capture;
those checks cannot be treated as free in a released workflow. The roughly
21-second difference between its stage sum and worker total includes these
checks, output capture and other untimed driver work. Dense
solves the two RHS together; FMM uses two sequential GMRES solves, its current
workflow. All three large-case controls in this table ran serially in fresh processes,
including a repeated FMM run that captures peak RSS through exact-row validation.
The earlier concurrent correctness pilot is retained separately. Treat these
as host-specific measurements, not portable speed ratios.

The independent Dense control also checks every row of the FMM solution against
the full physical matrix: maximum physical/scaled backward errors are
4.39e-17/6.88e-15. This check is in a separate process
and is not included in the FMM capacity peak. The full residual arrays are retained.

Large-case differences from Dense (all complex fields/densities retained):

| Method | Field relative maximum | Density relative maximum |
|---|---|---|
| FMM verified repeat | 1.23e-14 | 7.43e-12 |
| Existing Compressed | 2.53e-13 | 2.75e-10 |

The FMM repeat's complete density array is bit-identical to the earlier pilot,
so the independently computed full-matrix residual applies to both runs.
The complete FMM workflow uses 20.3% less peak RAM than existing
Compressed but takes 62.4% longer on this case. Its dominant retained
arrays are much smaller; the construction and validation peaks reduce the
practical RAM advantage. Retaining/reusing the exact validation-row cache is a
worthwhile follow-up, as is streaming its evidence instead of bulk staging it.

The FMM setup remains substantial: near-kernel evaluations dominate, and a
second approximate global operator is assembled to build the preconditioner.
Dropping that operator reduces retained RAM, not the work already spent building
it. The production Compressed control is essential: reduced iteration counts
alone do not establish that a new FMM backend beats the existing workflow.

## Conclusions and next work

* Keep Dense and Compressed. The study supports further FMM research, not replacing
  both backends or changing automatic routing.
* Integrate panel moments only within the research prototype for now. Combined
  near compression is useful when RAM matters; streamed near storage can be faster.
* Use a global approximate inverse as the leading preconditioner candidate.
  The tested local-only preconditioners are weak at increasing k, but this does
  not rule out Schwarz with a suitable global/coarse correction.
* Resolve the diagonal expansion's stability/error policy before production use.
  Test conservative/adaptive separation and a reusable wideband native plan;
  merely increasing expansion digits is counterproductive in this case.
* Reduce construction queries with a bounded cache or panel-block compression
  followed by nodal folding. Measure peak memory and real kernel calls, not only
  low-rank payload. Avoid materializing a second full near matrix for preconditioning.
* Test fixed points-per-wavelength growth, true PEC/dielectric coatings, high
  contrast, low loss/resonance, severe grading, and 1/16/181-angle sweeps. Those
  are not established by two angles on one homogeneous dielectric star.

This 8,192-unknown star at k=80 has roughly 97 perimeter wavelengths, about 42
panels per wavelength. A 20-foot span at 15 GHz is about 305 wavelengths across;
the present test cannot establish its capacity on a 32-GB desktop. Inverse ranks,
near work and stability must be measured as electrical size grows.

FMM is the main new acceleration studied here, but it is already combined with
a non-FMM global hierarchical inverse. H²/HSS factorization, coarse corrections,
bounded query reuse, mixed precision of preconditioners and disk-backed Dense
residuals remain distinct directions; no additional performance claims for
those unmeasured directions are made in this handoff.

## Evidence and scope

See `REPRODUCTION.md`, `ENVIRONMENT.json`, `SUMMARY.json`, `CLAUDE_TASKS.md` and
the hash-verified evidence archive. The analyzer recomputes 60 retained array
comparisons plus the large full-field comparisons. Full matrix tests were
performed before archiving selected worst columns; see
`FULL_MATRIX_ARCHIVE_SCOPE.json` for exactly what was retained and how to rerun.
All solve fields/densities and all random-vector operator outputs are retained.
No external messages were sent to Claude; this branch is the handoff for review.
