# Reproduction

Baseline commit: `98be27bc88bc53d78eff024ed60febc2d702d8dd`.
Candidate: the branch containing this report. Python/NumPy/SciPy versions and
production source hashes are in `SOURCE_IDENTITIES.json`.

Run from this audit directory. Unpack and independently recompute comparisons:

```bash
python unpack_evidence.py
python analyze_results.py > recomputed-analysis.json
```

The archive uses content-addressed payloads to avoid storing identical complete
arrays multiple times. Every restored file is size/hash checked. Physical fields,
densities, exact FMM validation rows and large full residual vectors are complete.
The two identical synthetic 512-RHS microbenchmark outputs are omitted (hashes
in the manifest); recreate them with `product_benchmark.py` using width 512,
shape 256 by 8192 and modes `baseline` / `candidate`.

Create separate baseline/candidate checkouts. Set these paths explicitly:

```bash
export GRIM_BASE_ROOT=/path/to/baseline-checkout
export GRIM_CANDIDATE_ROOT=/path/to/candidate-checkout
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
mkdir -p results
```

The low-level controls explicitly install a kernel-only CPU state, set
`reuse_operators=False`, and preserve double LU / Compressed release checks.
Check their `kernel_tables` arrays; empty arrays invalidate production-native
benchmark labeling. A fresh worker includes cold table construction.

```bash
GRIM_ROOT="$GRIM_BASE_ROOT" python dense_control.py '{"n":4096,"k":80,"out":"results/dense-production-4096"}'
GRIM_ROOT="$GRIM_BASE_ROOT" python compressed_control.py '{"n":4096,"k":80,"out":"results/compressed-production-4096"}'
GRIM_ROOT="$GRIM_BASE_ROOT" python compressed_control.py '{"n":4096,"k":80,"leaf":128,"out":"results/leaf-128-4096"}'
GRIM_ROOT="$GRIM_BASE_ROOT" python compressed_control.py '{"n":4096,"k":80,"eta":2.0,"out":"results/eta-2.0-4096"}'
GRIM_ROOT="$GRIM_BASE_ROOT" python compressed_control.py '{"n":4096,"k":80,"quantize_inverse":true,"out":"results/quantized-inverse-4096"}'
```

The quantization flag belongs only to this audit driver. It is not a production
option. It converts the completed inverse, so it cannot establish a lower
construction peak. The source `event.preconditioners[].bytes` describes its
original build; `inverse_bytes` reports the post-conversion retained size.

Implementation checks and alternating paired timing:

```bash
GRIM_ROOT="$GRIM_CANDIDATE_ROOT" python check_products.py > results/product-checks.json
python run_products_checks.py
python run_physical_checks.py
python run_public_checks.py
python physical_product_benchmark.py > results/physical-product-paired.json
python product_benchmark.py '{"mode":"baseline","width":2,"out":"results/product-baseline-2"}'
python product_benchmark.py '{"mode":"candidate","width":2,"out":"results/product-candidate-2"}'
```

The runners use the two root variables above; the standalone Dense/Compressed
controls use `GRIM_ROOT`. Run timing workers sequentially, not concurrently.
Native fallback is exercised by `run_physical_checks.py`; it disables all four
native routes in that worker. `run_sweep.py` uses the baseline root through
`GRIM_ROOT`. Raw worker outputs record specifications, both table qualifications,
release metrics, timing breakdowns, full fields, and peak RSS through output.

For corrected FMM timing, build the external native FMM library as documented in
`../fmm-hybrid-corrections/REPRODUCTION.md`. That research library is not a new
production dependency. Configure its loader/runtime paths as in that handoff:

```bash
GRIM_ROOT="$GRIM_BASE_ROOT" python corrected_fmm_control.py '{"n":4096,"k":80,"out":"results/fmm-production-4096","detach_operator":true}'
GRIM_ROOT="$GRIM_BASE_ROOT" python validate_large.py > results/full-validation.json
python analyze_results.py > results/analysis.json
```

`validate_large.py` assembles the complete 8192-by-8192 matrix in a separate
post-timing worker. It checks all available large-case densities, saves complete
residual vectors and scales, and has its own separately reported peak. The
analyzer rechecks the residual formulas from those arrays; it does not reconstruct
the full matrix. Re-run the validator for an independent operator reassembly.

Native Horner experiment: `native_unroll_experiment.c` is rejected research source.
To reproduce, place it as `far.c` in an isolated copy of the production native
directory and call `build_one(..., 'far')` from the existing `build.py`; restart
the Python worker before timing. Do not replace distribution libraries with it.
The first SIMD-loop-only pilot is preserved as a patch in
`native_simd_experiment.patch`. Neither pilot demonstrated a benefit.
