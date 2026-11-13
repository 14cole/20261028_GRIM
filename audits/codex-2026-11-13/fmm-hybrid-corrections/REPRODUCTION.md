# Reproduction

Research only. Production is pinned to `09fec5b2663649e859f292211c9d490e6b9f615b`;
the containing branch preserves all production blobs of `bfc5240`. Python,
NumPy, SciPy and platform identities are in `ENVIRONMENT.json`.

Run in this audit directory (or its extracted evidence directory):

```bash
export GRIM_ROOT=/absolute/path/to/20261028_GRIM
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
mkdir -p results
python check_safe_cross.py > results/safe_cross.json
python run_square_baseline.py "$GRIM_ROOT" 1400 > results/square_original.json
python square_diag.py "$GRIM_ROOT" 1400 > results/square_corrected.json
python preconditioned_solve.py '{"n":512,"k":40,"pol":"TE","op_tol":0.001,"inv_tol":0.001,"dense_reference":true,"out":"results/pre-512-TE"}' > results/pre-512-TE.json
python combined_benchmark.py '{"n":1400,"shape":"square","permute":7,"mode":"moment_hybrid_nodal","tol":1e-13,"full":true,"require_compression":true,"out":"results/matrix-square-1400"}' > results/matrix-square-1400.json
python run_investigation.py > results/suite.log 2> results/suite.stderr
python refine_stadium.py > results/stadium_refinement.json 2> results/stadium_refinement.stderr
python combined_benchmark.py '{"n":1536,"shape":"stadium","k":[40,-0.8],"permute":19,"mode":"moment_hybrid_nodal","tol":1e-13,"full":true,"require_compression":true,"separation":3,"out":"results/matrix-stadium-sep3"}' > results/matrix-stadium-sep3.json
python preconditioned_solve.py '{"n":4096,"k":80,"pol":"TE","op_tol":0.01,"inv_tol":0.01,"out":"results/pre-4096-TE-verified"}' > results/pre-4096-TE-verified.json
python dense_control.py '{"n":4096,"k":80,"pol":"TE","out":"results/dense-4096-TE"}' > results/dense-4096-TE.json
python compressed_control.py '{"n":4096,"k":80,"pol":"TE","out":"results/compressed-4096-TE"}' > results/compressed-4096-TE.json
python analyze_results.py
```

The suite uses fresh processes, overlaps two correctness jobs, and runs the
operator performance comparisons serially afterward. Do not run other numerical
jobs during those performance comparisons. It uses one warmup configuration per
case, two warmups and seven timed products per operator in the performance rows.
The original parent orchestration log includes a pause while additional accuracy
tests finished: use worker JSON timings, not parent `DONE ... seconds` values.

`run_investigation.py` intentionally waits for a completed 512-panel smoke result
before attempting large solves. It runs two incidence angles, 0 and 47 degrees;
complete fields have 180 observation directions. Matrix tests retain full matrices
locally before evidence compaction. They can take minutes each. Allow several GiB
for the full raw matrices and Dense control. This is not a 32-GB capacity forecast.

Optional native control (the other tests no longer require an FMM2D library):

```bash
export FMM2D_LIBRARY=/path/to/pinned/fmm2d/lib/libfmm2d.so
# Add the compiler runtime directory to LD_LIBRARY_PATH if it is not installed.
python native_stadium_control.py > results/native_stadium.json
```

The measured library is FMM2D `7e7509ecd6ebe31b9292cb00825410b478f44808`, default
32-bit Fortran integers. Its SHA-256 is recorded in `ENVIRONMENT.json`. No native
binary is added to the repository by this handoff. The earlier native build and
licensing investigation remains in the preceding handoffs.

The evidence archive retains all solve fields/densities, full random-vector
operator outputs and exact validation rows. For full matrix experiments it keeps
the columns containing the largest 32 errors and a largest-reference entry;
`FULL_MATRIX_ARCHIVE_SCOPE.json` records the original full NPZ hashes and scope.
Those columns reproduce reported maximum-entry errors. Full Frobenius norms and
unseen entries require rerunning the full matrix commands. The complete unabridged
raw matrices were used for the checks reported here.

Run `python unpack_evidence.py /new/output/directory` to verify and extract all
parts, then `OPENBLAS_NUM_THREADS=1 python analyze_results.py /new/output/directory`
to independently recompute the retained comparisons. Existing output directories
are rejected to preserve evidence. Source and raw Claude blobs in
`claude_reference/` are verified against commit `597b591a60db239ac82b758b55e8f6116e095792`.
