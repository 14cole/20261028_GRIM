# Reproduce the fresh-run solver workflow study

Start with main at `95f87190956de9197f0d021b0497772818c6f532` and unpack [EVIDENCE.zip](EVIDENCE.zip) outside the checkout. The archive contains independent stage reports, Python scripts, raw measurements, field arrays for the numerical comparisons and an internal SHA-256 manifest. Experimental implementations are opt-in in the study directory. Each solver invocation can start on a machine with only the checkout, its normal dependencies and the supplied input.

## Backend, recovery and export

Use the Python environment for GHOST. The examples below assume Linux. Set `REPO` to the absolute repository path, run the commands from the extracted study root, and write new measurements to a separate folder. These wall timers start after Python imports. Each invocation starts a new process. The stock code reads the source file, captures inputs, computes the requested fields, writes run-owned recovery output and publishes a GRIM file. The harness reopens the final file, saves the complex array and deletes its temporary working directory. The case-level report records OS high-water process RSS, actual field shape, convergence outcome and nested stage timers. It does not time application launch, the separate desktop setup panel or screen drawing. `--trace` adds counts and inclusive timers to selected preparation calls. The separate diagnostic cProfile file was used to locate functions, not as a benchmark.

```sh
export REPO=/path/to/20261028_GRIM
export PYTHONPATH="$REPO/tools/GHOST"
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
mkdir -p fresh
python experiments/profile_workflow.py "$REPO/airfoil.geo" fresh/airfoil-auto1 --threads 2
python experiments/profile_workflow.py "$REPO/airfoil.geo" fresh/airfoil-auto5-360 --frequencies 5 --angles 360 --threads 2 --trace
python experiments/profile_workflow.py "$REPO/airfoil.geo" fresh/matched-5-compressed-1 --frequencies 5 --angles 360 --threads 2 --backend compressed --trace
python experiments/profile_workflow.py "$REPO/airfoil.geo" fresh/airfoil-auto10 --frequencies 10 --angles 180 --threads 2 --trace
python experiments/profile_workflow.py "$REPO/airfoil.geo" fresh/airfoil-auto15-180 --frequencies 15 --angles 180 --threads 2 --trace
python experiments/profile_workflow.py "$REPO/airfoil.geo" fresh/airfoil-sweep --frequencies 1,1.1 --angles 180 --threads 2 --trace
```

For the three-way 1 GHz comparison run the following nine cases in order with two threads, no `--trace`, and names `ab-<method>-<repetition>`. Methods base, interface and junction mean stock, `--trial`, and `--junction` respectively. Recorded order was base-1, interface-1, junction-1, junction-2, interface-2, base-2, interface-3, base-3, junction-3. Compare the complete two-polarization fields before interpreting a timing shift. The high-frequency airfoil runs are single observations. There are two matched 5 GHz runs per backend.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python experiments/kernel_checks.py fresh/quadrature-checks.json
python experiments/summarize_profiles.py experiments/runs fresh/recomputed-summary.json
```

For the segmentation control, use the provided `workflow/geometry/split-1.geo` and `split-2.geo`. On each, run `profile_workflow.py` with `--units meters --frequencies 5 --angles 180 --threads 2 --sizing local --workflow check`. Use `--workflow specified` for the base mesh. The input generator and material-only/local/global counts are in `workflow/local_segmentation.py` and `workflow/local-segmentation.json`. The field comparison uses the same ordered directions and both polarization channels of the final exported GRIM files.

## Independent probes and qualifications

| Study | Start inside the archive | Scope |
|---|---|---|
| Geometry input, topology and materials | `geometry/GEOMETRY.md` | Parse, validation, meshing, 16 material fixtures and independent planner/geometry checks |
| Desktop and HPC planning | `workflow/FINDINGS.md` | Sheet DOFs, per-frequency RAM estimates, bounded in-run plan reuse and partial-run behavior |
| Dense/Compressed and numerical alternatives | `numerics/RESEARCH.md` | Fresh fixed-mesh solves, analytical and same-mesh references, sampled physical equations, and links to separately labeled historical benchmarks |
| Single-run working memory | `ram/README.md` | RHS/projection buffers, many-region memberships, allocator/RSS measurements and public-channel hashes |
| Display and final export | `output/FINDINGS.md` | Synthetic output through the production recovery, export and data-presentation code |
| Bistatic, BoR and native dispatch | `other-modes/FINDINGS.md` | Wide bistatic grids, analytical sphere checks, native/fallback paths and binary manifest verification |

Machine load, native libraries, thread settings and disk free space matter. Record them and use identical input, mesh, incident angles and numerical gates in a paired comparison. Preserve both complex field channels and their ordered axes. A forecast, a reduction in one buffer, and a peak process-memory measurement answer different questions. This investigation provides no native 32 GB Windows or full HPC execution measurement.

The supplied `verify.py` checks the in-archive SHA-256 list after extraction. Run it from the extracted study directory with `python verify.py`.
