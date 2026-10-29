# User-controlled exploratory 2D runs

Edit the CONFIG block in `ghost_backend/run_local_monostatic_exploratory.py`,
then run this command from the repository root:

```powershell
python tools/GHOST/ghost_backend/run_local_monostatic_exploratory.py
```

Set `GEOMETRY_FILE`, `GEOMETRY_UNITS`, `FREQUENCIES_GHZ`, `AZIMUTHS_DEG`, and
`OUTPUT_DIR`. Relative paths resolve from your working directory; material CSVs
resolve beside the geometry. This runner solves 2D monostatic VV and HH. It
does not run BoR or bistatic cases.

Define the requested sweeps directly with inclusive NumPy ranges, as in the
script's current configuration:

```python
FREQUENCIES_GHZ = list(np.arange(1.0,10.0+1e-6,1.0))
AZIMUTHS_DEG = list(np.arange(0.0,360.0+1e-6,1.0))
```

These request 10 frequencies and 361 angles. The runner uses these lists as
defined, including the 360-degree endpoint.

Each frequency runs on one selected mesh. There is no base/fine comparison,
convergence-driven refinement, condition-number estimation, or strict quality
gate rejection. Even the usual explicit-N minimum of four panels per material
wavelength is disabled for this runner. You own mesh convergence. The original
geometry file is not edited.

## Direct mesh controls

The starting configuration is:

```python
MESH_MODE = "global"
PANELS_PER_WAVELENGTH = 20
BASIS_ORDER = 1
MESH_GRADING = False
FACTORIZATION = "adaptive"
```

This is a trial mesh, not a statement that twenty panels is converged.

| Mesh mode | What is solved |
| --- | --- |
| `global` | Replaces every segment's N with `-PANELS_PER_WAVELENGTH`. Uses the global controlling material wavelength, with applicable surface-wave sizing. |
| `geometry` | Keeps the geometry's N settings. Uses global sizing for wavelength-based N. |
| `certification_base` | Legacy preset: one initial coarsened P2 candidate when eligible, otherwise the P1 base mesh. |
| `certification_fine` | Legacy preset: one initial coarsened P3 candidate when eligible, otherwise the P1 mesh at the certification policy's fine density (currently 1.5 times). |

`PANELS_PER_WAVELENGTH` is a positive integer, used only in `global`.
The presets choose their own basis; `BASIS_ORDER` applies to `global` and
`geometry`. There are no selectable `fixed` or `local` mesh modes in this runner.

Both `global` and `geometry` start from the same already-drawn segments and
straight primitives. Neither merges or redraws them. Their difference is where
the subdivision settings come from:

- `global` uses the script's `PANELS_PER_WAVELENGTH` everywhere, replacing the
  file's N values in the in-memory solve copy.
- `geometry` preserves each segment's saved N: positive N means fixed panels
  per primitive, negative N means panels per wavelength, and N=0 means the
  backend's default density (currently 20). The script's
  `PANELS_PER_WAVELENGTH` is unused in this mode.

Both use global material-wavelength sizing for wavelength-based counts, plus
applicable surface-wave sizing. With the same basis and grading, `global` at
10 panels per wavelength and `geometry` with every saved N=-10 produce the
same mesh. `geometry` does not mean one panel per already-drawn primitive;
the saved N can still subdivide each primitive further.

With `MESH_GRADING = False`, manual modes use uniform subdivisions within
each primitive and add no corner/end/junction panels. With `True`, the backend
clusters and can add panels to resolve those features. This is a geometric
sizing rule, not a convergence test. Grading also controls the protected-end
clustering of the legacy higher-order presets. Presets otherwise retain their
own coarsening: wavelength counts are divided by four, or eight for sufficiently
dense inputs; fixed positive N is not coarsened. Their selection is per frequency
and can fall back to P1 for small/faceted inputs or certain material models.

Wavelength sizing rounds
counts per primitive, with the existing 0.05-panel ceiling tolerance, and never
uses fewer than one panel per primitive. It cannot merge drawn edges. Increasing
density on a faceted circle refines that polygon; it does not make the geometry
more circular. For wavelength-based modes, the mesh is sized separately at each
frequency. In `geometry` mode, positive saved N values keep their fixed panel
counts across frequencies when grading is off.

## Polynomial order and points per wavelength

`BASIS_ORDER` selects P1 (linear), P2 (quadratic), or P3 (cubic) interpolation
of the unknown boundary fields. The geometric primitives remain straight.
At the same panel count, higher order adds unknowns and quadrature work; it is
not automatically faster. Its benefit comes from using fewer panels for a
comparable field error. Small problems can be faster with P1.

The script deliberately calls the setting **panels per wavelength**. A P2 panel
has three interpolation nodes, including its two endpoints; P3 has four.
Because neighboring panels usually share endpoints, a long smooth boundary has
roughly `order * panels_per_wavelength` distinct nodes per wavelength. Interface
duplication and multiple field unknowns affect the actual matrix size.
Thus ten P1 panels, five P2 panels, and about three to four P3 panels have roughly
similar node density, but are not guaranteed to have equal accuracy.

There is no universal density at which GHOST converges. For a first P1 study,
**10–20 panels per controlling wavelength is a practical trial range**; the
existing backend default is 20. That range is a starting heuristic, not measured
convergence for your geometry. Try 10, 15, 20, and 30 in separate runs, then
decide whether further refinement changes the quantities you care about.
For P2, five to ten panels is a reasonable trial bracket at similar node density;
do not transfer a P1 acceptance decision to P2/P3 without comparison.

General wave-meshing guidance also distinguishes degrees of freedom from
elements: [COMSOL's wave-resolution documentation](https://doc.comsol.com/6.4/doc/com.comsol.help.aco/aco_ug_pressure.05.137.html)
discusses roughly 10–12 degrees of freedom per wavelength and about five quadratic
elements. That is context from a different formulation, not a GHOST validation
result. Its [electromagnetic BEM documentation](https://doc.comsol.com/6.4/doc/com.comsol.help.rf/rf_ug_radio_frequency.07.091.html)
also describes wavelength-dependent boundary resolution and element-order choices.

Use the material wavelength, not just the free-space wavelength. In a simple
low-loss dielectric, wavelength is approximately the free-space wavelength
divided by `sqrt(epsilon_r * mu_r)`; GHOST also accounts for applicable bound
surface waves. Sharp edges, junctions, narrow gaps, resonances, and fine geometry
can need substantially more local resolution than a wavelength rule suggests.

You choose the comparison tolerance. For example, compare complex far fields,
VV/HH peaks and angular features, and phase where the field is appreciable.
Use an absolute field scale around deep nulls, where relative error or dB
differences can exaggerate a tiny change. A small linear-system residual only
means the selected discrete system was solved accurately; it does not establish
mesh convergence. The script performs none of these mesh comparisons for you.

## Factorization and speed

| Factorization | Behavior and tradeoff |
| --- | --- |
| `adaptive` | Default. The planner selects an admitted dense/hierarchical/compressed path using cost, RAM, and available timing evidence. Can retry another admitted backend after a numerical/resource failure on the same mesh. This is backend selection, not adaptive mesh refinement. |
| `dense` | Assembles the dense matrix. Usually uses direct LU for smaller systems. Large systems can use checked hierarchical factors with LU fallback; the name does not force LU. |
| `auto` | Legacy dense-matrix factor policy, including the hierarchical crossover. It does not provide the full `adaptive` planner's compressed-backend selection. |
| `hierarchical` | Requests a hierarchical factor of a dense assembled matrix. Compresses off-diagonal structure; effectiveness depends on rank and geometry. Still needs dense assembly storage and performs residual checks/refinement. |
| `compressed` | Uses the compressed assembly/operator path, avoiding the full dense system matrix. Useful when dense storage dominates; compression work and rank growth can make it slower on small or difficult cases. |

The default hierarchical crossover is currently about 10,000 unknowns, but
measured timing evidence can change it. For a diagnostic run that must use LU,
choose `dense` and set `GHOST_HIERARCHICAL_MIN_UNKNOWNS=0` in the launching
environment. This is an existing process-level backend setting.

There is no universally fastest factorization. Start with `adaptive`; for tiny
cases, explicit `dense` avoids automatic selection overhead. The largest speed
control is usually the number of unknowns. Dense storage grows approximately
with its square and LU work with its cube; halving unknowns can therefore cut
those components by about four and eight respectively, not necessarily total
runtime by those factors.

Thread counts, incident-field compression, and compressed storage sizing use
the backend's automatic defaults. Memory admission uses available memory.
These resource controls are not exposed in the script.
`ANGLE_BATCH_SIZE` (1–256) groups incident angles while reusing the factorization.
Frequencies still require separate systems. This runner uses double precision
and CPU execution, matching the configured backend's supported fast path.

`TEMPORARY_DIRECTORY` can select an existing absolute path for temporary data.
`MAX_PANELS` is a resource cap you can raise or lower, not an accuracy threshold.

## Results and remaining checks

A unique run directory contains `requested_settings.json` and one VV/HH `.grim`
per completed frequency. Earlier exports remain if a later frequency fails.
The console reports elapsed time, actual panel count, and selected backend.
Result metadata contains the effective execution settings and
`exploratory_mesh`, including the selected N values, polynomial order, grading,
and `convergence_owner="user"`. Results are explicitly uncertified.

Quality diagnostics are retained and failures are printed without blocking
export. Geometry/material validity, supported formulations, finite numerical
results, memory admission, panel caps, node tolerances, and algebraic solver
checks remain. Compression/residual refinement may do additional algebra on
the same mesh. These are distinct from mesh-convergence testing. Production
entry points retain their existing grading and explicit-density defaults.
