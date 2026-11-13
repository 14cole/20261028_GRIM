# Reproduction and evidence scope

This is research based on commit `59cf19aad4fd562610b94e8cfe643a68036cdd18`. Production files are unchanged. New scripts are audit-only; they are not exposed by the GUI or solver routing.

## Verify the recorded evidence

From this directory:

```sh
python unpack_evidence.py /tmp/fmm-hybrid-evidence
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python /tmp/fmm-hybrid-evidence/analyze_study.py
```

The unpacker checks every archive part, the complete archive and every extracted file. The analyzer recomputes the stored product differences, retained full-matrix maximum differences, field differences and comparison tables.

Complete physical far-field arrays and densities are included for every TE/TM result. All output rows are retained for random-vector operator tests. Large sampled-reference tests retain every checked reference row. For complete-matrix tests, every column was tested, but the published compact archive keeps complete columns containing the 20 largest entry differences plus the maximum reference entry. The original full-matrix file hashes and selected columns are recorded in `FULL_MATRIX_ARCHIVE_SCOPE.json`. Published maximum-entry errors can be recomputed from these columns; a full Frobenius-norm check requires rerunning the complete-matrix experiment. No whole-matrix archive is implied.

## Fresh experiments

Use a new writable copy of the extracted directory, keeping the original evidence intact. Install NumPy and SciPy; original versions and environment limits are in `ENVIRONMENT.json`. The optional scheduling wrappers additionally use psutil. Set the production root and the separately built FMM2D library:

```sh
export GRIM_ROOT=/absolute/path/to/20261028_GRIM
export FMM2D_LIBRARY=/absolute/path/to/libfmm2d.so
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
# Set LD_LIBRARY_PATH if the Fortran runtime is outside the system library path.
```

The library is the same pinned default-int32 FMM2D build as in the inherited solver-methods/FMM investigations. No new external library was built or distributed. The wrappers import it even in some Python-cached cases. Build details are in the parent `solver-methods-research` evidence; the exact library hash is in `ENVIRONMENT.json`.

Run a case directly to preserve your environment settings:

```sh
python benchmark.py '{"n":2048,"k":[40,0],"mode":"stream","out":"/tmp/new-stream"}'
python benchmark.py '{"n":2048,"k":[40,0],"mode":"hybrid_nodal","tol":1e-13,"out":"/tmp/new-hybrid"}'
FMM_NDIV=100 python benchmark.py '{"n":2048,"k":[40,0],"mode":"native_tuned","out":"/tmp/new-native"}'
python system_case.py '{"n":512,"k":40,"kind":"TE","star":true,"engine":"hybrid_nodal","tol":1e-13,"incident_angles":[0,47],"gmres_max_cycles":6,"preconditioners":["fmm_near_ilu"],"out":"/tmp/new-system"}'
```

The benchmark writes raw arrays to the `out` prefix and prints its JSON record to stdout. Redirect that JSON to the matching `.json` file when adding it to an evidence directory. The analyzer locates arrays by the basename of each record's output prefix.

Suite definitions are in `run_suite.py` (smoke, scale, difficult, low, large), `run_native_tuning.py`, `run_systems.py`, `run_extensions.py`, `run_last_comparisons.py`, and `run_repeats.py`. These retain the original host's `LD_LIBRARY_PATH`; adapt that assignment for your runtime. Run numerical cases serially when comparing time or peak RAM. Each recorded case ran in a fresh process. The asynchronous waiting wrappers document orchestration only and assume the original host paths.

Additional checks:

```sh
python coated_quadrature.py "$GRIM_ROOT"
python structural_checks.py
python panel_projection_proof.py
```

The quadrature diagnostic accepts either the original complete matrices or the retained worst-entry columns. It uses the normal near dispatcher plus independent raw-Hankel Gauss integration. The structural check verifies exact-once pair coverage, transpose data sharing, complex-symmetric application and reordered subset queries of the nodal oracle.

## Measurement limits

- Operator timings are medians of three single-vector applications, with all raw repetitions retained. Peak RSS includes setup and a two-RHS application before dense validation. Retained-byte accounting excludes Python object/allocator overhead; use process RSS for measured peak comparisons.
- The common refinement study fixes a unit-radius five-lobed star at k=40. It stresses crowded near leaves as panel count increases; it is not a high-frequency scale scan or a universal desktop-capacity estimate.
- Small full-matrix checks and large random-vector checks establish different levels of evidence. Neither replaces a mesh certificate or final complete-solve acceptance.
- System runs keep dense reference matrices/scaling and a common streamed-near ILU alive. Their memory is not standalone hybrid solver memory.
- Concentric contour tests exercise primitive operators across a narrow gap, not a complete multi-region coated-body formulation.
