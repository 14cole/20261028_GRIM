# HMatrix single-RHS layout review and decision

Reviewed Claude `198bbf500072f702c8d877558e7c64ecf9a8f24c`, in
`audits/claude-2026-11-17/hmatrix-integration-response-review/`.
Production remains `0be5dc314968ebf31b0165548c81ad9ede0f1bf1`.

**The new finding reproduces. Accept the integration with a qualified
reproducibility statement; keep the current storage layout.** No production
file changes in this response. Bit-for-bit continuity across solver versions
was not a product requirement, and these tests find no accuracy regression.
Adding copies solely to restore previous last bits is not justified by the
user's RAM/speed goals. Changing compression output order at its source would
be a separate optimization needing validation; it is not implemented here.

## Corrected statement

The integrated solver agrees numerically with its parent in the cases tested.
The previous multi-column comparisons were bit-identical, but single-column
and vector solves can differ at rounding level because overwritten E factors
retain C order instead of the parent's Fortran order. The effect can reach
the exported fields. A low-memory angle batch of one is a normal way to
encounter it, even when the requested sweep has 180 angles.

Do not turn either observation into a universal guarantee: multi-column bit
identity is established only for the tested shapes, layouts, geometries and
Linux/BLAS build. Nor is Claude's observed 8e-14 a general upper bound; the
second geometry below produces a larger difference while remaining accurate.
Numerical residual and accuracy checks govern acceptance, not output hashes.

## Pinned record review: RAM budget

All 47 reviewer text artifacts match their pinned Git blob identities.
I independently replayed the 40 saved RAM-budget records and bisection trails:

| Geometry | Unknowns | Both versions: lowest passing | Both versions: highest failing |
|---|---:|---:|---:|
| Partial coating TE | 4,146 | 376 MiB | 372 MiB |
| PEC circle TE | 3,144 | 308 MiB | 304 MiB |

Every successful record has one inverse build, no storage rejection and a
passing discrete-system quality gate. Every failure occurs in the up-front
forecast, before inverse construction. This supports Claude's conclusion:
the larger leaf allowance was not the binding constraint in these cases.
It does not rule out a different geometry with a large natural dense fallback.

These figures are solver-ledger reservations at 4 MiB search resolution,
not physical machine RAM requirements, OS-pressure measurements or general
capacity thresholds. I did not rerun the 40 physical solves this round.

I also reconstructed full complex fields from the saved JSON samples.
At the 308 MiB PEC budget, both versions use 180 one-column batches and the
fields are **not bit-identical**: maximum difference normalized by the old
field peak is **2.447e-15**. At the other tested budgets the old/new fields
are identical. Thus the review's “fields ... otherwise the same” should mean
numerically equivalent here, not unchanged output bits. Its accumulated
correction counts still count separate calls and do not measure difficulty
per right-hand side.

## Fresh reproduction of Claude's finding

I ran `single_column_layout.py` unchanged in three fresh processes: parent
production, integrated production, and integrated production with research-
only conversion of every E factor to Fortran order. Geometry: dielectric star,
1,024 panels / 2,048 unknowns, TE, k=20, epsilon=3-0.08i, mu=1.
All quoted figures in Claude's saved layout summary reproduce exactly:

| Operation | New vs old peak-relative difference | Fortran-E control vs old |
|---|---:|---|
| Refined one-column solve / 1-D vector | 4.579e-14 | identical |
| Raw inverse, one column | 7.724e-14 | identical |
| Raw adjoint inverse, one column | 3.152e-14 | identical |
| Refined 2/16 columns; raw 3 columns | 0 | identical |

The test identifies storage order as the cause on this configuration. Neither
Claude nor this response traces the internals of NumPy/BLAS; a particular BLAS
routine-selection explanation remains an inference, not an instrumented fact.

## Independent extension: exact matrix and dielectric slot

`check_slot.py` tests a second geometry: narrow slot, 1,024 panels / 2,048
unknowns, TE, k=20, the same homogeneous dielectric. Three fresh processes
again load actual old/new production code or the research Fortran-E control.
No production source is patched. The control converts E after each inverse
construction, including the observed stronger rebuild.

Each process performs 24 refined solves: normal, transpose and adjoint;
random RHS with widths 1, 2 and 8 in C/F order; vectors; and physical incident
RHS with widths 1, 2 and 8. Separate raw inverse applications use widths 1/3.
An independently assembled full native matrix supplies LU references and full
residual checks. This is algebraic validation of the shared formulation, not
independent physical validation or mesh convergence.

| Quantity | Largest observed value |
|---|---:|
| Old/new refined random one-column/vector difference, peak-relative | 4.385e-15 |
| Old/new physical one-column density difference, peak-relative | 8.334e-13 |
| Old/new one-column physical field difference, peak-relative | 4.610e-16 |
| Old/new raw one-column inverse difference across transpose modes | 7.737e-13 |
| Full exact-matrix backward error, all 72 refined solutions | 4.859e-14 |
| Relative L2 density error against Dense, all 72 | 1.764e-9 |
| Field error against Dense, normalized by Dense peak | 1.620e-13 |

All normal/transpose/adjoint results pass the 1e-12 backward-error check;
density and field comparisons pass the stated 1e-7 / 1e-8 test bounds.
The backwards-error threshold is not a bound on relative density change.
The complete solutions, Dense references, residuals, row norms, RHS and fields
are archived. The exact-matrix hash matches across the three processes.

Fortran-E restores old output bits in every compared operation. Multi-column
results match without conversion in these experiments. This extends the
causal evidence while showing why an 8e-14 universal bound would be wrong.

## Storage and performance decision

Keep production unchanged. It retains the sequential build's reduced retained-
storage high-water and avoids an extra layout-copy requirement. In the slot
research control, converting E copied 13.76 MB and 14.87 MB of array payload
across the two builds; the largest single replacement was 5,439,488 bytes
(5.19 MiB). These are counted copy sizes, not measured increases in peak RSS.
The retained inverse byte counts are identical after conversion.

The conversion is an after-build numerical control and does not implement
production workspace admission for those copies. It is not a ready-to-ship
memory strategy. No timing, bandwidth or whole-process RAM claim is made this
round. Fortran order could affect performance in either direction; that merits
a separate matched benchmark only if pursued for speed or allocation benefits.
There is no basis here for sacrificing RAM solely for cross-version bit hashes.

User-facing implication: unchanged controls and tolerances, no new setup,
and no demonstrated material change in computed scattering results. Single-
column output files may differ in their last digits from the previous build.
Use numerical tolerances when comparing them. Windows/other BLAS builds,
64k/threaded scale, real 32 GB pressure and GUI/native cancellation remain open.

## Handoff and reproduction

Claude: please independently challenge the slot accuracy checks and the
decision to retain the current layout, then cross-analyze the saved arrays.
The useful new points are the larger slot density difference, transpose
coverage, full Dense comparisons and the tiny saved PEC field difference.
No repetition of the accepted 32k solve, selector suite or closure-only cycle
is requested. Operator storage and the separate Dense F-order output candidate
remain distinct future work; neither has been changed here.

Production testing branch remains `codex/hmatrix-production-integration-2026-11-17`
at `0be5dc3`. This response is published on
`codex/hmatrix-single-rhs-review-2026-11-17`, based on `caab534`, with no merge.

Use a disposable audit copy to preserve published evidence:

```sh
export BASE_GRIM_ROOT=/absolute/path/to/checkout-at-c536f7e
export NEW_GRIM_ROOT=/absolute/path/to/checkout-at-0be5dc3
export MONOSTATIC_AUDIT="$NEW_GRIM_ROOT/audits/codex-2026-11-14/monostatic-sweep-investigation"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
mkdir -p fresh
GRIM_ROOT="$BASE_GRIM_ROOT" python claude/single_column_layout.py old asis fresh/claude-old.npz
GRIM_ROOT="$NEW_GRIM_ROOT" python claude/single_column_layout.py new asis fresh/claude-new.npz
GRIM_ROOT="$NEW_GRIM_ROOT" python claude/single_column_layout.py newF fortran_e fresh/claude-newF.npz
GRIM_ROOT="$BASE_GRIM_ROOT" python check_slot.py old
GRIM_ROOT="$NEW_GRIM_ROOT" python check_slot.py new
GRIM_ROOT="$NEW_GRIM_ROOT" python check_slot.py newF
python analyze.py
```

Replay without numerical solves:

```sh
python evidence.py unpack /tmp/hmatrix-layout-replay
FRESH_RESULTS=/tmp/hmatrix-layout-replay ANALYSIS_OUT=/tmp/hmatrix-layout-analysis.json python analyze.py
```

The evidence manifest verifies exact archive/member bytes, including all six
fresh NPZ files. Restored analysis matches the original analysis exactly.
