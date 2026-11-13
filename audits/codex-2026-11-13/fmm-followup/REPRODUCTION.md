# Reproduction and evidence

The new research starts from `codex/solver-methods-research-2026-11-13` commit `8777e23eba7730dd94af05b706d08c4f27c9ef29`. Production code remains at the prior `09fec5b2663649e859f292211c9d490e6b9f615b` content. All additions are in this audit directory. The experiment uses existing compiled assembly kernels and the previously built FMM2D research library; it does not replace shipped DLL or .so files.

## Unpack and inspect

Run `python unpack_evidence.py /absolute/path/to/new-evidence-directory`. It verifies archive-part checksums and every extracted file. The archive contains raw resource traces, JSON metrics, complete complex product/field arrays, sampled exact references, small-system densities, scripts, pinned Claude evidence and the unchanged validation log. `scripts/` provides reviewable source without unpacking. Failed attempts, if any, are retained and identified in the handoff.

The resource observer samples summed process-tree RSS every 25 ms and PSS/USS every 200 ms. RSS double-counts shared pages across fork workers. PSS is preferable for physical use, but is sampled, not a guaranteed high-water mark. `ru_maxrss` measures the process high-water mark; it excludes children. Sampling introduces contention, so unmonitored timing controls are separate. Setup/product high-water marks captured before exact-reference assembly exclude the later validation buffers; whole-run observer peaks do not.

The host had four CPU equivalents, 16 GiB, Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0. Exact identities are in `ENVIRONMENT.json`. Measurements are not performance predictions for a 32 GiB desktop or for Windows.

## Fresh reruns

Copy the extracted Python helpers and `claude_reference/` to a new output directory. Do not rerun over archived JSONs: runners skip existing nonempty results. Set:

```bash
export GRIM_ROOT=/absolute/path/to/20261028_GRIM
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
```

Run suites sequentially, without other CPU-heavy jobs. The waiting logic only coordinates scripts in the same directory; it is not a scheduler for unrelated workloads.

```bash
python claude_reference/validate.py > claude-validation-rerun.log
python run_angle_cases.py
python run_galerkin_cases.py
python run_holdouts.py
python run_extra_cases.py
python run_unmonitored_large.py
python run_phase_refinement.py
python near_scaling.py
python analyze_followup.py
```

`run_angle_cases.py` repeats small thread comparisons and measures the full 181-angle case. `run_galerkin_cases.py` qualifies S/K/K'/W against direct assembly before large products and complete PEC/TE/TM systems. `run_holdouts.py` tests the final streaming near construction, large point products and complex loss, then repeats timing without a resource observer. `run_extra_cases.py` checks a tight Nyström solve against the dense same-discretization operator and a complex analytical cylinder field.

The original expansion-order/separation grid used `cached_fmm_accuracy_stage.py`, before streaming near construction and panel partitioning were introduced. To reproduce that grid, use a separate output directory with this file copied to `cached_fmm.py`, then run `run_point_cases.py`. The final `cached_fmm.py` is used by all holdouts and Galerkin tests. Do not silently substitute one variant's memory measurements for the other. The final implementation additionally contains a bounded all-near fallback for an electrically small minimum-depth tree. `initial_low_frequency/` preserves the pre-fix source and failing complete-system runs. To reproduce those failures, use that `cached_fmm.py` in a separate fresh script directory. `rerun_low_frequency.py` coordinated preservation and reruns in this session; fresh final-version suites do not require that preservation step. `make_cached_variant.py` and `upgrade_cached.py` record how the audit derivative was made; the final source is authoritative.

Small full-system runs deliberately retain dense validation and use dense-derived row/column scales. Their peak memory is not an FMM-only capacity result. The near-field ILU coefficients come from the FMM's integrated near blocks, but a production scaling scheme still needs investigation. Exact-reference residuals are not a mesh certificate.

## Native comparison library

Use FMM2D commit `7e7509ecd6ebe31b9292cb00825410b478f44808` and the build instructions in the preceding `solver-methods-research/REPRODUCTION.md`. Set `FMM2D_LIBRARY` to the absolute shared-library path. The bridge assumes 32-bit Fortran INTEGER; a default-integer-8 build is incompatible. The local library SHA-256 is recorded in `ENVIRONMENT.json`. No new native library is needed for the NumPy/SciPy reusable-plan implementation.

The runner records the session's custom `LD_LIBRARY_PATH`; adjust it for another custom runtime. A nonexistent directory is harmless if libgfortran is installed normally.

FMM2D's root Apache-2.0 license and retained GPL-2.0-or-later source notices remain unresolved for distribution. No upstream FMM2D source or binary is included in this archive. No Windows build or validation is claimed.
