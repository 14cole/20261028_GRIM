# Running 2D solves

The GHOST solver tab separates mesh workflow from the linear solver.
Automatic is the default linear-solver policy for 2D monostatic runs. Dense and
Compressed remain explicit Advanced choices. Changing the mesh workflow does not reset
the selected backend, manual polynomial order, or corner grading.

## What you choose

| Setting | Values |
| --- | --- |
| Geometry and units | A `.geo` file or the Geometry tab; inches or meters. |
| Frequencies | A list or a start/stop/step sweep in GHz. |
| Azimuths | A list or a start/stop/step sweep in degrees. |
| Scattering mode | Monostatic, or bistatic with observation angles. |
| Mesh workflow | Solve specified mesh; Check specified mesh; Find converged mesh automatically. See below. |
| Comparison target | Standard, or tight (1% maximum complex change) for the base/fine comparison. The dB and phase changes are compared where the pattern is above -30 dB of its peak (deep nulls are judged by the complex change). |

## Mesh workflow in the GUI

- **Solve specified mesh:** use the geometry's N values and the sizing,
  polynomial order, and grading selected in Advanced. Solve one mesh per
  frequency, with `mesh_convergence_certified=false`. Condition estimation,
  residual checks, numerical validity checks, and density limits remain active.
- **Check specified mesh:** solve that mesh and a finer copy at the same
  polynomial order, using the selected linear solver. Publish the finer result
  only when both polarizations pass the existing comparison criteria. Failed
  Local sizing can retry Global material sizing, with the same backend.
- **Find converged mesh automatically:** the previous checked/adaptive startup
  behavior, now explicit. Eligible cases start with coarsened P2/P3 candidates;
  comparison failures can trigger refinement and a P1 reference fallback.
  This option applies to 2D monostatic runs only. BoR and bistatic retain the
  specified-mesh single/checked workflows and their existing numerical paths.

Mesh agreement is numerical evidence for the requested fields and tolerances;
it is not proof that the geometry or material model represents the real object.
The reported certificate and quality metadata retain their existing meanings.

The one-shot preset and certification checkbox have been replaced by this
workflow selector. Specified-mesh order and sizing are retained when visiting
Automatic and restored when returning; the workflow does not change the selected
linear-solver policy. Automatic may select different backends as mesh size changes;
explicit Dense and Compressed requests remain fixed. Backend-specific details and
fallbacks remain part of the chosen solver. There is no universal fastest backend.

For an already validated mesh, select **Solve specified mesh**, open Advanced,
and match its polynomial order, sizing, and grading. Positive N specifies
panels per drawn primitive; N=0 or negative N still requests wavelength sizing.
An existing certified result's refined mesh is not automatically reused.
Leave the linear solver on Automatic for budget-aware selection, or compare explicit
Dense and Compressed on the same mesh and frequency for your particular workload.
A larger single P1 solve can take longer than an automatic checked P2/P3 pair.
The GUI makes no promise that an unchecked solve is the fastest configuration.

The original checked/adaptive startup behavior remains the default. Batch
configuration field names and solver entry points are unchanged. New profiles use
`factorization="automatic"`; older versions cannot read that new value. Saved explicit
Dense/Compressed choices are preserved.

## What is automatic

Monostatic runs:

- **Backend.** Automatic first admits candidates against the solve RAM budget.
  It prefers dense LU below 10,000 forecast unknowns and compressed execution
  at or above that size, using an admitted alternative if the preference cannot
  fit. This conservative policy is not a universal speed crossover. It does not
  read or write timing history. Adaptive refinements are admitted again.
  Automatic compressed execution permits H-matrix from 1,024 unknowns, retaining
  tile support for small systems, excluded formulations and rejected assembly.
  Explicit Compressed keeps its existing 8,192-unknown threshold. Dense uses LU
  unless an explicit hierarchical/launch or legacy timing override requests HODLR.
  BoR retains its existing factor policy.
  Within compressed solving, the planner prices operator storage, inverse
  construction, assembly workspace and angle batches. Retained storage uses
  the remaining reservation after phase workspace, without a 2-GiB minimum.
  Paired hierarchical assembly is used only when the active plan admits it;
  otherwise the polarizations are assembled separately. Eligible smaller
  systems may use hierarchical assembly when the tile forecast exceeds the
  reservation and the hierarchical forecast is lower. A reusable polarization
  partner retains its existing representation when it is repriced.
- **Memory.** The current reservation starts from 90% of available physical
  RAM, subject to explicit user and scheduler limits and live physical/commit
  checks. It remains tied to that initial physical allowance; verified growth
  in the operating system's commit limit does not remove the physical cap.
  Assembly sample growth receives incremental checks across concurrent tasks.
  Forecasts are estimates, not guarantees of completion for every geometry.
- **Mesh in the automatic workflow.** An adaptive polynomial mesh: a quadratic candidate with a cubic
  accuracy check, local refinement when the comparison fails, and a global
  linear mesh as the final fallback.
- **Numerics.** Double-precision LU, automatic incident-field basis reuse, and
  up to 256 angles per batch. Large hierarchical interaction lists start from
  a cheaper compression proposal; the probe checks, backtracking and error
  thresholds remain unchanged. Small dense blocks inside the compressed inverse
  can avoid unnecessary mesh retries; they do not select the dense backend.
- **Threads.** Automatic BLAS uses one thread for H-matrix condition probes,
  inverse applications and the full RHS compression/solve operation. Dense LU
  retains its parallel BLAS policy. Explicit numeric BLAS settings remain honored.
  Assembly threads default to the physical cores of the solving
  machine (at most 16), or the per-unit allocation a batch driver computed for
  a scheduled solve. Compressed tile operators are
  assembled in worker processes instead: up to eight (half the host cores) for
  a desktop solve, the CPU reservation for a scheduled solve, fewer when
  memory is short, and none inside batch worker processes. Factorization and
  angle solves choose a BLAS pool by system size within the CPU reservation:
  one thread through 256 unknowns, up to four through 1024, up to eight through
  2048, then the available reservation. Explicit integer `blas_threads` values
  are caps and are never widened. `linear_algebra_execution` records the actual
  library pools used; these thresholds are a policy, not a speed guarantee.
- **Frequency scheduling.** Desktop sweeps can run two
  frequencies at once when the predicted work justifies startup and their
  combined CPU and RAM reservations fit. Larger units run first; results
  retain the requested frequency order. These workers share the total CPU
  budget and do not start nested assembly workers. Small runs and runs that
  cannot fit two frequencies remain sequential. A frequency that outgrows
  its worker reservation is retried in the parent after the workers drain.
- **Compressed assembly reuse.** Admission samples retain up to 32 MiB of
  verified tiles for assembly of the identical operator. An already assembled
  polarization partner supplies its actual storage size. Assembly workers
  persist for the run and refresh their geometry and coefficients before each
  operator; their retained memory is included in later phase forecasts.
- **Run recovery.** Every Start Run computes fresh results. Each completed
  frequency is saved in this run's unique recovery folder with both
  polarizations and its accuracy information. Parallel workers save directly
  to disk and release their completed fields instead of sending a growing
  collection to the GUI. Earlier runs are never reused by Start Run.

Bistatic runs use dense LU on the global linear mesh, with the same validated
CPU kernel tables and native far assembly as monostatic runs. Their bounded
table state spans polarization and certification passes and is released when
the request completes or is canceled. `cpu_kernel_execution` records table
validation and use. Explicit mixed-precision API calls use the same kernel
tables and factor with mixed-precision LU; explicit GPU calls keep their
existing execution path.

## Batch drivers

Edit the CONFIG block of `ghost_backend/run_local_monostatic.py` or
`ghost_backend/run_hpc_monostatic.py`:

| Setting | Meaning |
| --- | --- |
| `FRD_DIR`, `OPN_DIR` | Input geometry folders, searched recursively. |
| `FREQUENCIES_GHZ`, `AZIMUTHS_DEG` | The sweep. |
| `OUTPUT_DIR` | Output root; each run gets a new timestamped folder. |
| `GEOMETRY_UNITS`, `MESH_CERTIFICATION`, `ACCURACY_TARGET` | As in the GUI. |
| `WORKERS` (local) | Optional ceiling on concurrent solves. |
| `MAX_SOLVE_GB` | Optional per-solve RAM ceiling in GiB. |
| SLURM settings (HPC) | `N_NODES`, `N_JOBS`, `ARRAY_THROTTLE`, partition, account, QoS, walltime, cores and memory per node, mail, extra `#SBATCH` lines, job prologue, `PYTHON_EXE`, `SUBMIT`. |

Both drivers cost every geometry/frequency unit from the mesh the solver will
build, run the most expensive units first, and admit concurrent solves against
the machine's or node's memory. 2D drivers do not read JSON configuration
files, and portable HPC bundles are for BoR requests.

## User-controlled exploratory 2D run

Use `ghost_backend/run_local_monostatic_exploratory.py` for a single-mesh
VV/HH solve with user-owned convergence. Edit its CONFIG block and run:

```powershell
python tools/GHOST/ghost_backend/run_local_monostatic_exploratory.py
```

The current configuration uses a global P1 mesh at 20 panels per controlling wavelength,
with corner grading off and compressed factorization by default. Choose
panels per wavelength, P1/P2/P3 interpolation, optional grading and factorization.
CPU counts, memory admission, incident-field compression and compressed storage
use automatic backend defaults. Frequency and azimuth sweeps use the configured
NumPy ranges, including their requested endpoints.
The original geometry and initial certification-candidate modes remain available.

No mesh comparison, error-driven refinement, condition estimation, strict
quality-gate rejection, or explicit-N density-floor rejection runs. Input,
resource and algebraic checks remain. Every completed frequency is exported
immediately, with requested settings saved alongside the uncertified results.

See [the exploratory run guide](EXPLORATORY_RUNS.md) for all mesh modes,
factorization tradeoffs, points versus panels per wavelength, and how to judge
convergence yourself. This runner supports 2D monostatic scattering only.

## Recovering an interrupted desktop run

2D and BoR desktop runs create `Run_Recovery/run_<timestamp>_<unique ID>`
beside the input geometry. Unsaved Geometry-tab inputs use the application's
Documents/GRIM Outputs directory. The folder contains:

- `inputs/`: the captured geometry, material CSV contents and solve settings.
  Workers read these captured copies, so later edits to the original files do
  not change an active run. Open `inputs/geometry.geo` in the solver to run it
  again, using the units recorded in `README.txt`; keep its material CSVs beside it.
- `completed/`: ordinary `.grim` files written as each frequency finishes.
  Open or drag these into GRIM's results viewer just like a final export;
  `run.json` is not needed for viewing an individual file. BoR files preserve
  the requested radar grid and embedded body model. Bistatic runs have one
  file per frequency and incidence angle.
- `frequencies/`: internal recovery records plus checksums. Files
  are flushed and published atomically; incomplete or damaged outputs are
  excluded from recovery.
- `run.json`: the run's identity, requested frequencies, input checksums and
  status. Completion is checked against the actual frequency files, so an
  abrupt process exit does not require a final status update.

The `.npz` records support exact solver-result recovery and should not be
renamed to `.grim`. The directly loadable files are in `completed/`. Older
recovery folders from before this feature can still be opened through
**Recover Completed Run** and exported using **Export Last Result**.

In the Solver tab's Tools section, choose **Recover Completed Run** and open
that run's `run.json`. Completed frequencies become available for plotting
and **Export Last Result**. Missing frequencies stay missing, and a partial
export is marked as partial in its metadata. Recovery does not start or
resume a solve; Start Run always starts a new run.

Final `.grim` export joins frequency planes incrementally and includes the
captured input files for provenance. It does not assemble the entire field
grid in memory. Successful complete exports are verified before publication
is recorded. Their recovery folders are removed when the result is no longer
being viewed, provided the final exported files still match their checksums.
Interrupted, unexported, partially exported and failed-export runs are kept.
The cleanup includes `completed/`, so copy individual frequency `.grim`
files elsewhere if you want to retain them separately from the final export.
Writing these native files adds per-frequency disk space and I/O; it does not
retain completed frequencies in RAM or rerun the numerical solver.

Solve-time output memory is limited to active frequencies; result viewing
loads one frequency at a time. Solver matrices, run metadata and arrays used
for a particular plot still require memory. Recovery preserves completed
frequencies, not an unfinished frequency's matrix or factorization.

## Status reporting

The status text reports assembly, factorization, angle solving and mesh
certification work, with elapsed solve time and sampled process RAM. Base and
fine mesh phases are identified separately. The percentage can remain fixed
while a long stage runs. RAM is sampled every 50 ms and includes other work in
the same process; it is not an exact allocation peak. Stage timings in exported
metadata are inclusive and may overlap.
For parallel frequency runs, the largest individual worker peak is reported
separately from reserved RAM. It is not the simultaneous process-tree peak;
aggregate sampled RAM is left unavailable when it was not measured.

## Python API

Public 2D solve functions still accept `execution_options` for tests,
benchmarks and diagnostics. Production runs do not need it; they use
`ghost_backend.execution.options.automatic_run(scattering)`.

Every desktop Start Run computes fresh results for both 2D and BoR. Cross-run
solve caching and automatic resume are disabled. Existing application-cache
checkpoints are ignored. Run recovery is used only for explicit inspection
and export of completed outputs, never to skip a requested calculation.

`ghost_backend.execution.fresh_sweep.run_fresh(..., frequency_workers='auto')`
retains the desktop's bounded parallel frequency scheduler. The desktop passes
a newly created `RecoveryRun` as `recovery=...`; completed fields are saved
and the returned sample sequences load a frequency only when needed. Without
that argument, API results remain in memory and count against the run's RAM
allowance. Direct solve calls retain their normal sequential frequency loop.
Legacy explicit checkpoint utilities remain separate from desktop execution.

The explicit experimental option below remains off in automatic runs:
`compressed_far_method='verified_cur'` proposes low-rank far tiles but checks
every coefficient before acceptance. It is not a general speed guarantee.
Every frequency builds a fresh inverse; experimental frequency inverse reuse
has been removed. Saved profiles with `frequency_preconditioner='off'` still
load, with that retired field removed. An explicit request to enable reuse
raises an error asking the caller to remove the setting.
