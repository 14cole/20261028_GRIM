# Reproduction

Run from this audit directory in the published branch. Set `GRIM_ROOT` to the checkout root (the folder containing `tools/GHOST`). Use a clean process for each measurement:

```sh
export GRIM_ROOT=/absolute/path/to/20261028_GRIM
export GHOST_AUDIT_ROOT="$GRIM_ROOT"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
mkdir -p results
python unpack_evidence.py
```

The archived `growth-*` runs profile the accepted source at `65ebfe6`, which has the same production content as this branch's parent. To reproduce those baselines, point `GRIM_ROOT` at a separate checkout of `65ebfe6`. Profiling overhead is included; do not compare these wall times directly with unprofiled runs.

```sh
python profile_growth.py '{"n":8192,"k":160,"out":"results/repro-growth-16384"}'
python profile_growth.py '{"n":16384,"k":320,"out":"results/repro-growth-32768"}'
```

For the new production candidate, point `GRIM_ROOT` at this branch. The norm benchmark alternates old and new routines on the same physical operator for six rounds and asserts bitwise equality. It saves the full field and density from the production solve.

```sh
python check_norms.py
python norms_benchmark.py '{"n":2048,"k":40,"threads":1,"out":"results/repro-norms-4096"}'
python norms_benchmark.py '{"n":2048,"k":40,"threads":4,"out":"results/repro-norms-4096-threaded"}'
python norms_benchmark.py '{"n":2048,"k":40,"pol":"TM","eps":[4,0],"star":false,"out":"results/repro-norms-TM"}'
python norms_benchmark.py '{"n":8192,"k":160,"out":"results/repro-norms-16384"}'
python bor_hierarchical_probe.py
python claude/claude_adjoint_probe.py > results/repro-adjoint.json
python netlib_adjoint_probe.py
python regression/run_all.py
```

The Netlib probe requires the Debian Netlib library path recorded in that script; change it explicitly on another host. It exercises CBLAS directly and does not switch NumPy's linked BLAS.

Research only: compile a separate paired-panel library derived from this checkout's unchanged native far kernel. It is never installed into `tools/GHOST`.

```sh
python build_pair_kernel.py
python validate_native_pairs.py
python check_native_fallbacks.py
python native_fmm_control.py '{"n":2048,"k":40,"op_tol":0.01,"inv_tol":0.01,"detach_operator":true,"native_pairs":false,"profile":false,"dense_reference":true,"out":"results/repro-fmm-reference"}'
python native_fmm_control.py '{"n":2048,"k":40,"op_tol":0.01,"inv_tol":0.01,"detach_operator":true,"native_pairs":true,"profile":false,"dense_reference":true,"out":"results/repro-fmm-native"}'
```

`validated_solve_seconds` ends after the independent exact-row validation and field output, before the optional full Dense comparison. `peak_through_validation_gib` also excludes that later Dense comparison. External whole-process peak/time include Dense validation and are preserved separately. The FMM trial has no mesh or condition certification and is explicitly not a production backend.

To reproduce external whole-process timing/peak records, prefix a command with `python measure.py results/label --`, for example `python measure.py results/repro-native -- python native_fmm_control.py '{"n":2048,"k":40,"op_tol":0.01,"inv_tol":0.01,"native_pairs":true,"out":"results/repro-native"}'`. The measuring parent owns exactly one child.

Run timing cases serially. Preserve native table event logs. Do not substitute scripts lacking `CPUState(kernel_only=True)` or compare loose preconditioner tolerances of 1e-3 against 1e-2 without labeling the difference.

Larger matched FMM controls (8,192 unknowns), with independent exact-row checks. Dense full-field references from the preceding corrected benchmark are included in the evidence archive for comparison; those reference arrays are unchanged.

```sh
python native_fmm_control.py '{"n":4096,"k":80,"op_tol":0.01,"inv_tol":0.01,"detach_operator":true,"native_pairs":false,"profile":false,"dense_reference":false,"out":"results/repro-fmm-8192-reference"}'
python native_fmm_control.py '{"n":4096,"k":80,"op_tol":0.01,"inv_tol":0.01,"detach_operator":true,"native_pairs":true,"profile":false,"dense_reference":false,"out":"results/repro-fmm-8192-native"}'
```

The large near-block validation archive uses lossless reference-plus-XOR packing to avoid duplicating nearly identical complete matrices. XOR acts on integer representations of floating-point bits; there is no lossy subtraction or rounding. Reference bytes are transposed before ZIP compression; observer-normal reference K is also encoded as a lossless XOR against transposed source-normal K. These transformations reconstruct every original floating-point bit, including departures from exact symmetry. This command verifies all 28 complete arrays against their SHA-256 hashes and optionally restores ordinary NumPy arrays:

```sh
python pack_pair_arrays.py results/native-pair-validation.npz results/native-pair-validation-unpacked.npz
```
