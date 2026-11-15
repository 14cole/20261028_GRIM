# Reproduction

Research only, based on commit `27afe8f3fb523a0a61f2a99ebb77e9e2708f16d7`.
Production code and solver accuracy gates are unchanged. The prototype hooks
are installed in isolated Python processes only.

From a checkout of this research branch, use absolute paths:

```sh
export GRIM_ROOT="$PWD"
export MONOSTATIC_AUDIT="$GRIM_ROOT/audits/codex-2026-11-14/monostatic-sweep-investigation"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export STUDY_DIR="$GRIM_ROOT/audits/codex-2026-11-15/dense-compressed-memory-research"
cd "$STUDY_DIR"
```

The inherited monostatic harness imports its adjacent `research/` modules.
These Dense/Compressed runs do not invoke the experimental FMM native kernel.
Use NumPy/SciPy and the production native libraries; environment versions,
source hashes, cgroup limits and source provenance are recorded separately.

To inspect original evidence without computing new solutions:

```sh
python unpack_evidence.py /tmp/dense-compressed-replay
RESULTS_DIR=/tmp/dense-compressed-replay/results ANALYSIS_OUT=/tmp/replayed-analysis.json python analyze.py
```

This verifies archive/array hashes and repeats comparisons. It is **array
replay**, not an independent solve, matrix assembly, or fresh residual check.
Original NPZ ZIP hashes are provenance only; restoration preserves all array
bits and each array's C/F layout. All logs, failures and original incomplete
capture records are also restored. See `CAPTURE_NOTE.md`.

Fresh serial reproduction (the runner refuses to overwrite existing timed
cases; use a clean copy of this study directory without a `results/` folder):

```sh
python run_suite.py suite1.json
python run_suite.py suite_adjoint.json
python run_suite.py suite_geometry.json
python residual_benchmark.py
python run_suite.py suite_scale.json
python check_layout.py
python run_suite.py suite_geometry_capture.json
python run_suite.py suite_sweeps.json
python run_suite.py suite_layout.json
python residual_layout_benchmark.py
python residual_output_benchmark.py
python run_suite.py suite_lifecycle.json
python run_suite.py suite_output.json
python run_suite.py suite_output_repeats.json
python analyze.py
```

`suite_geometry.json` is retained for historical completeness; new independent
material validations should use the corrected `suite_geometry_capture.json`.
The full analysis expects both suites because both are part of the published
experiment record. Each case gets a fresh process and stdout/stderr/time record.
Suites preserve failed cases and continue; inspect return codes, not just the
suite runner's exit status. Dense and Compressed share identical inputs for
each matched comparison. Thread counts are 1 except the requested four-thread
20-foot PEC cases and explicitly labeled four-thread microbenchmarks.

The star harness uses production factors directly, with fresh exact-row checks
but without production condition admission or mesh certification. The physical
material runner uses the production condition and strict discrete quality
gates. Neither establishes mesh convergence or physical validation against an
analytic/independent scattering solution.

The disk microbenchmark advises eviction of its own temporary file only and
records actual process read-byte counters. It neither exhausts machine RAM nor
tests out-of-core LU. The 32,768-unknown Compressed comparisons have no fresh
full Dense reference on this 16 GiB environment.

For the independent review, write down hypotheses and acceptance criteria,
perform your own fresh checks first, then cross-analyze these results. Record
which findings come from new solves, new equation evaluations, array replay,
source inspection, or another model's measurements.
