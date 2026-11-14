# Reproduce this research

This folder uses the production code and native Linux libraries in its parent
repository. Set `GRIM_ROOT` to the checkout root. Research helpers are included
under `research/` with their original provenance in `research_sources.json`.
They do not change production modules on disk. One research hook temporarily
replaces near-pair quadrature only while the research FMM builds its near blocks.

```bash
export GRIM_ROOT=/absolute/path/to/20261028_GRIM
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
(cd research && python build_pair_kernel.py)

# Verify the supplied evidence without rerunning solves:
python unpack_arrays.py restored
MONOSTATIC_RESULTS="$PWD/restored/results" \
  MONOSTATIC_ANALYSIS="$PWD/restored/analysis.json" python analyze.py

# Fresh measurements, preserving the supplied evidence:
export MONOSTATIC_RESULTS="$PWD/reproduced/results"
export MONOSTATIC_ANALYSIS="$PWD/reproduced/analysis.json"
python check_projection.py
python check_batched.py
python check_rhs_batching.py
python check_block.py
python check_block_cadence.py
python run_suite.py suite1.json
python run_suite.py suite2.json
python run_suite.py suite3.json
python run_suite.py suite4.json
python analyze.py
MONOSTATIC_RANK_OUTPUT="$PWD/reproduced/rank-scan.json" python rank_scan.py
```

Run the suites serially, with no other numerical jobs. The runner skips cases
with existing `.time.json` files, including failures: choose a fresh results
folder or move existing evidence before rerunning. Failed launches/results are
preserved, never silently overwritten. Suite 2 can take substantially longer
than the small correctness tests. All cases use one assembly/BLAS thread.

The `measure.py` wrapper reports fresh-process wall time and high-water RSS.
The runner additionally separates setup, RHS generation, solving, matched
monostatic projection, exact-row validation and evidence serialization.
`compute_seconds` is setup + RHS + solve + projection, excluding the extra audit
validation and NPZ serialization. Peak RSS includes these audit costs; it is
not the production memory planner's forecast. Independent coefficient rows
remain resident during solving and their bytes are reported.

Each NPZ batch retains the full complex densities, original RHS, matched field,
angle grid, validation row IDs, exact residuals and exact row norms. This is not
an RCS-only comparison. The analysis checks every solution against Dense at the
same geometry/frequency/polarization/grid where that reference was run. Acceptance
limits are 1e-8 peak-normalized complex field difference and 1e-7 maximum
per-angle density relative L2 difference; independent rowwise backward error
must be below 1e-12. These checks are not mesh or condition certification.

Angles use `linspace(start, stop, count, endpoint=False)`, so -90 to 90 with 180
samples is -90 through 89 degrees; 0 to 360 with 360 samples is 0 through 359.
GHOST defines incident angle toward the source. Its monostatic observation uses
the same angle, as in production `twod/fields.py`; no extra 180-degree shift is
appropriate. `check_projection.py` tests matched projection against the diagonal
of the complete bistatic grid for arbitrary complex densities.

These are research harness measurements, not GUI or complete distribution
benchmarks. Factors and production residual checks are reused; mesh certification,
frequency changes, GUI overhead, and export formatting are outside the timings.
Production's assembly-session plane-wave load cache is not exercised by this
standalone harness, so field/RHS timings are not an end-to-end production forecast.

`krylov=batch_gmres` means **batched independent GMRES**, not a mathematical
block Krylov space. Each column has its own Arnoldi/least-squares problem, using
twice-orthogonalized Gram-Schmidt; only operator applications are shared as matrix
operations. All original RHS must meet the same true scaled residual limit.
`check_batched.py` compares against a dense solve and exercises duplicate/zero
RHS. `recycle` instead uses SciPy LGMRES with eight retained augmentation vectors
and the previous solution as the initial guess; `lgmres_cold` discards those
vectors and starts from zero for each angle. GMRES inner and LGMRES outer callback
counts are different units; compare true operator-call counts and time.

For `krylov=rhs_qr`, entries in the JSON `angles` work-counter list describe QR
basis solves; their legacy `angle` values are basis indices, not physical angles.
The physical incident grid is always the NPZ `angles` array and the JSON spec.
The reconstructed solutions and all original illuminations are checked separately.
The largest previous-solution trial is a 24-angle, one-degree probe; it is not
labelled or extrapolated as a measured full 180-angle sweep.

The analysis's `matvecs` count includes the extra accurate FMM check of every
original illumination after QR reconstruction. For batched GMRES it reports
RHS-equivalent applications (batch applications times width); the raw block
records also give actual traversal counts. Neither is an estimate of FLOPs.

A further experiment, `krylov=block_gmres`, uses a **shared block Krylov space**,
with twice-orthogonalized block Arnoldi and QR/small-SVD rank deflation. It checks
true residuals for every original RHS and retains at most 21 blocks per restart
(168 basis columns for width 8). This differs from the 81 vectors *per RHS* in
batched independent GMRES. Rank-aware work counters sum actual column widths.
Run `python check_block.py`, then `python run_suite.py suite3.json`, then rerun
`python analyze.py`. The smoke check includes duplicate and zero RHS. These are
research implementations, not additions to the shipped solver.

The default FMM construction-operator and inverse tolerances are both 0.01.
Suite 3 also tests stronger 0.001 and 0.0001 preconditioners. Only the approximate
preconditioner changes: accurate FMM and every original-RHS acceptance limit
remain unchanged. Setup, inverse storage and iteration cost must all be counted.
Construction-operator storage stays complex64; the accurate FMM remains double.

The evidence archive preserves numerical arrays bit for bit, consolidating the
original batches into one NPZ per case. It does not reconstruct original ZIP
bytes or original batch file layouts. Original batch-file hashes remain in the
archive index for provenance; reconstructed-array hashes are checked separately.
JSON timing/solver records and complete stdout/stderr logs are also included
and hash-checked on restoration.

Dense reference cases use double precision and explicitly retain the original
matrix in RAM. Suite 3 additionally exercises the existing `disk` residual
storage policy with 16- and 256-angle batch limits. Disk storage keeps the LU in
RAM and streams the original coefficients for full residual checks; it is not
an out-of-core LU factorization. `/proc/self/io` deltas, where available, separate
logical reads from actual block-device reads. Fresh processes do not imply a
cold filesystem cache. High-water process RSS excludes reclaimable filesystem
page cache; disk-case RSS is therefore not total system memory consumption.

RHS generation can differ by roundoff across batch widths. `check_rhs_batching.py`
checks widths 16, 64 and 256 independently of the solve. Array comparisons require
identical angle grids and RHS agreement within 5e-15 (both peak-normalized and
maximum per-angle relative L2), and report whether RHS arrays were bit-identical.
This is separate from—and does not loosen—the original solver residual gates.
For a fresh RHS-to-archived comparison, run
`MONOSTATIC_RESULTS="$PWD/restored/results" python check_rhs_batching.py`.

`evidence-verification.json` records the local comparison of every restored array
against its original batch bytes. `verify_evidence.py` is that internal check and
requires the original batch NPZs; `unpack_arrays.py` is the portable verifier for
the supplied consolidated archive.

Suite 4 contains two focused 24-angle controls at the strongest preconditioner:
scalar GMRES and shared block GMRES with true residual checks every four steps
(and at restart/breakdown). Final original-RHS acceptance is unchanged. Compare
these with the saved first 24 angles of the suite-3 full block sweep; do not
label their timing difference as a measured full 180-angle speedup.

Restored arrays use C-contiguous storage. The analyzer canonicalizes loaded
arrays to that same order so norm-reduction roundoff is reproducible across
original Fortran-ordered batches and restored evidence. Numerical values are
unchanged; the local roundtrip checked all array bytes in logical C order.
