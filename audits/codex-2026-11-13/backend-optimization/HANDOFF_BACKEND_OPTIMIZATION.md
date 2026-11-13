# Backend optimization implementation and investigation handoff

Date: 2026-11-13. Publication parent: `98be27bc88bc53d78eff024ed60febc2d702d8dd`
(`codex/fmm-hybrid-corrections-2026-11-13`). This continues the review of Claude
commit `597b591a60db239ac82b758b55e8f6116e095792`.

## What ships

Two existing production files change, with one small shared helper added:

- `linalg/products.py`: compute an adjoint product by conjugating the RHS and
  owned output when their combined byte count is smaller than the factor.
- `compressed/hmatrix.py`: use that helper for complete and arbitrary-submatrix
  transpose/adjoint product dispatch.
- `linalg/hierarchical.py`: use it in the shared hierarchical inverse recursion.

The identity is `A.H B = conjugate(A.T conjugate(B))`. Each output is owned;
inputs stay unchanged. Wide batches retain the previous expression when it
requires fewer copied bytes. No coefficient precision, quadrature, compression
threshold, residual gate, sample-row gate, thread allocation, or mesh policy
changes. Transpose and normal products retain their existing arithmetic.

This targets Compressed adjoint/condition work and the shared hierarchical
inverse, including opt-in Dense HODLR and its BoR callers. **It does not make
ordinary 2-D Dense LU factorization faster or reduce its quadratic storage.**
No GUI options change. There are no native ABI changes or new DLL/SO requirements;
all shipped native sources and libraries remain byte-for-byte unchanged.

## Important correction to the previous performance handoff

The old `dense_control.py` and `compressed_control.py` invoked low-level assembly
without a `CPUState`. That bypassed validated kernel tables and native far
assembly. `execution_scope` alone does not enable them. Those results were valid
fallback-path numerical comparisons, but they were mislabeled as representative
production timing. **Do not continue quoting 249/267/434 seconds or the former
20%-RAM/62%-time FMM comparison as the normal CPU workflow.**

The corrected drivers install a kernel-only state with operator caching disabled,
as the public wrappers do. They retain the requested factorization policy. All
runs below use one assembly/BLAS thread, cold fresh workers, and include table
construction. Public survey smoke checks for PEC and dielectric, Dense and
Compressed, independently confirm tables in `metadata.experimental_cpu.kernel_tables`.
They also preserve baseline/candidate fields exactly.

Matched case: five-lobed star, 4,096 P1 panels / 8,192 unknowns, exterior k=80,
epsilon=3-0.08j, TE, incidences 0 and 47 degrees, 180 observation directions.
There is no mesh or condition certification in this timed control. Dense LU is
explicitly double precision and keeps residual coefficients in RAM. Compressed
uses production tolerances and release checks. These are controlled CPU timings,
not a prediction for automatic GUI thread counts, mixed LU, or disk residuals.

| Method | Assembly/setup s | Factor s | Two RHS s | Worker total s | Complete peak GiB |
|---|---:|---:|---:|---:|---:|
| Dense LU | 28.83 | 21.03 | 1.389 | 51.47 | 2.132 |
| Compressed | 42.56 | 7.27 | 0.469 | 50.56 | 0.555 |
| Research FMM + loose compressed inverse | 228.60 | 2.01 | 14.292 | 250.06 | 0.377 |

FMM's setup includes 30.38s for the loose
compressed operator and 198.22s for its FMM operators. Its
39/42-iteration solves still use the previous research algorithm. All three
methods now get the same kernel-table execution context. FMM uses
32.0% less complete
peak RAM than Compressed but takes 4.95 times
as long. The FMM peak includes exact-row verification and evidence output, not
just the iteration phase. The separate full-matrix validation peak is excluded
from all timed solve capacity numbers and recorded independently.

The new Dense result differs from the old SciPy/fallback Dense result by
4.00e-15 in normalized maximum field amplitude and 5.38e-14 in density.
Independent full-matrix residual validation covers every large experimental
solution, not only sampled rows: worst scaled backward error
1.329e-13, below 1e-12. Maximum field
difference from Dense among those cases is
3.537e-13. Full residuals, scales, RHS,
densities and fields are archived. These measurements do not certify mesh error.

## Measured benefit of the implementation

The physical paired benchmark constructs one 4,096-unknown dielectric operator
and inverse, warms both methods, then alternates baseline/candidate order over
eight rounds. Median of the final six rounds:

| Operation, two RHS | Old | New | Reduction |
|---|---:|---:|---:|
| H-matrix adjoint product | 30.31 ms | 20.83 ms | 31.3% |
| Refined adjoint inverse | 89.25 ms | 70.37 ms | 21.1% |

A fresh-worker 256-by-8192 complex factor product with two RHS reduced peak
RSS from 102.11 to 72.04 MiB (about 30 MiB) and median product time from 9.33 to
6.26 ms. A 64-RHS product improved from 24.01 to 16.10 ms. A 512-RHS product
selects the unchanged direct expression; its timing differences are noise,
not an optimization. These are operation-level gains, **not a claim of a 31%
faster complete solve**. Separate physical-worker timings varied enough that
the alternating paired test was necessary. Raw timings for both are retained.

Validation:

- 105 direct helper cases: empty axes, vector/batched RHS, C/F/strided/reversed
  layouts and mixed real/complex dtypes; no input mutation.
- Shared Dense HODLR and Compressed inverse tests against a full nonsymmetric
  complex matrix, normal/transpose/adjoint, one/four threads, arbitrary shuffled
  submatrices, empty selections, and in-place inverse recursion.
- Lossy-star TE, lossless-circle TM, and strongly lossy dielectric checks;
  the last explicitly disables native far, near, scatter and table kernels.
- Eight public PEC/dielectric Dense/Compressed baseline/candidate runs.
- 126 archived array comparisons. All implementation-only
  comparisons are bitwise identical on this Linux/NumPy/BLAS environment.
  Bitwise equality on a different BLAS/CPU is not promised.

Full-scale BoR and Windows runtime performance were not measured. The shared
inverse arithmetic is exercised, but Claude should include platform/BoR tests.

## Other investigations: promising, not enabled by default

### Cluster size and admissibility

Same 8,192-unknown star and unchanged accuracy gates:

| Setting | Worker total s | Operator + inverse MiB | Peak GiB |
|---|---:|---:|---:|
| Default leaf 256, eta 1 | 50.56 | 440.0 | 0.555 |
| Leaf 128, eta 1 | 48.44 | 377.1 | 0.492 |
| Leaf 64, eta 1 | 51.75 | 384.0 | 0.500 |
| Leaf 256, eta 1.5 | 48.92 | 397.9 | 0.517 |
| Leaf 256, eta 2 | 46.41 | 396.7 | 0.513 |

Smaller leaves can reduce memory, but there is a real tradeoff. On a lossless TM
circle with 4,096 unknowns, leaf 128 versus 256 reduced retained storage from
162.4 to 128.6 MiB and peak from 0.263 to 0.230 GiB, while time rose from 17.88 to
21.53 seconds. On the higher-frequency, more lossy star, time was approximately
unchanged and savings were smaller. Raising eta to 2 is promising on the large
star, but only one electrical/geometry case was tested. The current defaults
remain unchanged. A geometry-aware policy needs broader PEC, coated/multi-region,
close-gap, graded/P2/P3 and high-frequency validation, not a universal new constant.

### Reduced-precision inverse factors

Research-only post-build conversion of `v12`, `v21`, `e1`, `e2` to complex64,
keeping authoritative operator coefficients, LU corrections/leaves, residuals
and release checks in double precision:

- Inverse retained bytes: 149,397,352 -> 94,793,576, a 52.07 MiB saving.
- Total dominant retained storage drops about 11.8%.
- Both RHS pass full physical/scaled residual validation; no GMRES or rebuild.
- Refinement grows from two to three steps; observed two-RHS solve time grows
  from 0.469 to 0.674 seconds. That timing is a single trial, not a stable ratio.
- Peak remains about 0.55 GiB because the double-precision inverse was built
  first. **This is not yet a larger-model capacity improvement.**

Next experiment: create compact factors during recursion, with explicit
construction accounting, overflow checks, transpose/adjoint and condition-probe
coverage, wide-RHS costs, and reliable double rebuild on failed release checks.
Casting authoritative H-matrix coefficients to complex64 is a different change
and is not justified by these results.

### Native Horner rewrites

Two loop rearrangements were compiled and tested on Linux. They produced the
same solve fields but did not demonstrate a speed benefit in the pilot
(3.68/3.60 s versus 3.43 s profiled baseline assembly at 2,048 unknowns).
The baseline was profiled and these were single trials, so no precise regression
ratio is claimed. Neither rewrite nor rebuilt library is shipped. The unrolled
source and raw results remain as negative evidence.

## Recommendation and questions for Claude

1. Review the benchmark-context correction first. Independently reproduce the
   corrected Dense/Compressed/FMM comparison and confirm public wrapper behavior.
2. Audit the adjoint helper's byte-based crossover, input ownership, strided
   dispatch and in-place inverse recursion. Repeat on Windows/another BLAS and
   include a BoR hierarchical condition-estimation case.
3. Reproduce the paired physical operation benchmark. Quantify complete
   condition-estimation benefit separately from normal forward solve time.
4. Investigate geometry-aware leaf/eta choices, using actual full fields,
   independent coefficients and peak memory. Do not weaken operator/release gates.
5. Investigate in-construction mixed inverse storage. Establish whether retained
   savings survive the build peak and whether condition probes trigger rebuilds.
6. FMM remains research: these corrected results strengthen the case for improving
   Compressed first. A larger-case crossover still needs proof; neither one result
   nor the previous timing error rules out FMM at larger electrical size.

No new user-facing choices are needed for this implementation. Continue optimizing
the current backends; adopt cluster/mixed-storage policies only after their
capacity and accuracy tradeoffs are demonstrated across the outstanding cases.

## Evidence and reproduction

See `REPRODUCTION.md`, `SOURCE_IDENTITIES.json`, `EVIDENCE_MANIFEST.json`,
`unpack_evidence.py`, and the numbered evidence archive parts. Full physical
fields/densities and large-case residual vectors are included. The two identical
62-MiB synthetic 512-RHS product outputs are excluded; their hashes, exact seed,
shape and regeneration command are recorded. No physical field arrays are omitted.
