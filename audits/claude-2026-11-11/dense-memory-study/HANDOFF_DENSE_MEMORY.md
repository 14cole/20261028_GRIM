# Dense memory: residual copy on disk and one polarization at a time (handoff for Codex)

- **Tree measured:** production `distribution/grim-open-item-fixes-2026-11-11` at `d162169`. No code changed.
- **Host:** Linux, 4 vCPU, 15 GiB, Python 3.13, temporary directory on a local virtual disk (ext4). No Windows, no network file system.
- **Question:** can Dense run in less memory, so that it can be used more often as the reference method?
- **Evidence:** scripts and raw results beside this file (73 profiled solves).

## Answer

Yes. Both levers already exist in the code and together cut the Dense peak from about 3.2 matrices to 1.2 to 1.5 matrices, with fields unchanged. The problem is that the solver cannot reach that configuration on its own: the memory forecast does not know about it, so Dense is refused, and Automatic switches to Compressed, at budgets where lean Dense would fit.

One matrix is 16 bytes × N². "Matrices" below means peak process memory above the interpreter baseline, divided by that.

| Case | Unknowns | Default Dense | Lean Dense (both levers) | Time cost |
|---|---|---|---|---|
| PEC circle | 8,000 | 3.21 GiB, 30 s | 1.47 GiB, 41 s | +35% |
| Airfoil 3 GHz | 8,666 | 3.66 GiB, 27 s | 1.60 GiB, 32 s | +20% |
| Coated circle | 9,720 | 4.56 GiB, 40 s | 1.90 GiB, 51 s | +28% |
| PEC circle | 14,000 | 9.29 GiB, 104 s | 3.65 GiB, 137 s | +32% |

For comparison, Compressed (H-matrix) on the same host: coated 9,720 unknowns 2.49 GiB and 117 s; airfoil 3 GHz 0.85 GiB and 64 s; PEC 14,000 unknowns 1.92 GiB and 104 s. Lean Dense beats Compressed on both memory and time for the coated case, and on time for the airfoil. At 14,000 unknowns Compressed is better on both.

## Where the Dense peak comes from

Profiled with a 10 ms memory sampler and marks at each factor's creation, LU, first solve and release (`profile_dense.py`). For PEC, coated and airfoil bodies the peak is always during the first polarization's solve and consists of:

1. the first polarization's matrix (kept for the residual check);
2. its LU factor (a second copy);
3. the second polarization's matrix, already assembled;
4. about 0.2 to 0.5 of a matrix in solve workspace and caches.

The dielectric circle is different: its two polarizations are never held together, so its default peak is 2.2 matrices.

## Lever 1: residual copy on disk (`dense_residual_storage='disk'`)

The original matrix is written to a temporary file and the LU overwrites it in memory. Residuals are then computed by reading the file back in row blocks.

| Case | Unknowns | Memory | Disk | Saved | Time |
|---|---|---|---|---|---|
| PEC | 4,000 | 0.95 GiB | 0.72 GiB | 0.23 | 7.9 → 9.3 s |
| PEC | 8,000 | 3.21 | 2.28 | 0.93 | 29.8 → 32.9 s |
| Dielectric | 8,000 | 2.19 | 1.25 | 0.94 | 21.9 → 25.0 s |
| Coated | 6,480 | 2.13 | 1.53 | 0.60 | 16.3 → 17.0 s |
| Coated | 9,720 | 4.56 | 3.17 | 1.39 | 39.8 → 42.2 s |
| Airfoil 3 GHz | 8,666 | 3.66 | 2.57 | 1.09 | 26.7 → 28.9 s |
| PEC | 12,000 | 6.89 | 4.81 | 2.08 | 73.2 → 81.2 s |
| PEC | 14,000 | 9.29 | 6.45 | 2.84 | 103.9 → 115.9 s |

The saving is one matrix in every case. The time cost is 4 to 18 percent here. It needs free temporary disk equal to one matrix.

The `auto` setting behaved like `memory` in all eight cases with no RAM budget. It switched one factor to disk only once, under a budget of 2.4 GiB at 8,000 unknowns.

## Lever 2: one polarization at a time

`twod/assembly/session.py` `plan_paired_assembly` lets the TE step assemble the TM matrix in the same kernel pass, but only when the forecast plus one more matrix fits the budget. With a tighter budget the solver assembles each polarization separately.

| Case | Unknowns | Paired | Unpaired | Saved | Time |
|---|---|---|---|---|---|
| PEC | 8,000 | 3.21 GiB | 2.40 GiB | 0.81 | 30.2 → 37.2 s |
| Coated | 9,720 | 4.55 | 3.27 | 1.28 | 41.0 → 49.3 s |
| PEC | 14,000 | 9.29 | 6.49 | 2.80 | 104 → 122 s |

Saving: about one matrix. Cost: 17 to 23 percent, because the kernel pass is done twice. Pairing applies only to the `multi_region` formulation (which includes these PEC and coated cases); the dielectric circle is never paired.

## Fields

- Coated circle, 6,480 unknowns: all 362 amplitudes of lean Dense are bitwise equal to default Dense.
- PEC circle, 4,000 unknowns: maximum relative difference 6.5e-15 over 362 amplitudes.
- First amplitudes of the 8,000-unknown PEC runs are identical across `memory`, `disk` and `auto`.

I did not compare full fields for the larger cases.

## The defect: the forecast blocks the lean configuration

`twod/solver.py` `_estimate_memory_gb` prices the dense solve as `2*matrix + ...` whatever the residual storage setting. Consequences, measured:

| Case | Forecast | Lean Dense needs | What happens between the two |
|---|---|---|---|
| PEC, 8,000 | 2.33 GiB | 1.47 GiB | Explicit Dense is refused at 2.0, 1.7 GiB. Automatic picks Compressed at 2.4 GiB and below |
| Coated, 9,720 | 3.30 GiB | 1.90 GiB | Dense refused at 2.8, 2.2 GiB. Automatic picks Compressed at 3.4 GiB (97.5 s, against 49 s for Dense) |
| Dielectric, 8,000 | 2.33 GiB | 1.25 GiB | Dense refused at 2.0 GiB and below |
| PEC, 14,000 | 6.46 GiB | 3.65 GiB | Dense refused at 5.5 GiB and below |

So today the lean configuration is reachable only by setting `dense_residual_storage='disk'` by hand and choosing a RAM budget inside a narrow window (above the forecast, below the forecast plus one matrix). A user who lowers the budget to save memory loses Dense altogether.

## Side finding: Automatic fails at some budgets where neighbours succeed

Coated circle, 9,720 unknowns, Automatic:

| RAM budget | Result |
|---|---|
| 3.4 GiB | Compressed, 97.5 s |
| 2.8 GiB | **MemoryError** (`Compressed inverse projected inverse block requires 0.997 GiB additional allocation; 0.853 GiB is admitted`) |
| 2.2 GiB | Compressed, 118.7 s |
| 1.9 GiB | **MemoryError** (same message, 0.902 GiB admitted) |

A larger budget failing where a smaller one succeeds suggests the compressed plan chosen at 2.8 GiB is more ambitious than its admission allows. Lean Dense would have fitted at both failing budgets (1.90 GiB). I did not investigate the cause.

## Recommendations for Codex to evaluate

1. **Teach the forecast a lean Dense tier.** When the normal dense forecast does not fit, price Dense as unpaired with the residual on disk (about one matrix plus workspace; measured 1.2 to 1.5) and admit it if that fits and temporary disk is available. Automatic would then try: Dense, lean Dense, Compressed, in that order below the size boundary.
2. **Decide the order of lean Dense and Compressed above the boundary.** On this host lean Dense was better than Compressed for the coated body at 9,720 unknowns and worse for the PEC circle at 14,000. A fixed rule is not supported by four data points.
3. **Make `auto` residual storage follow the budget consistently.** It should choose disk whenever that is what makes Dense fit, not only in the one case seen here.
4. **Investigate the Automatic failures in the side finding.**
5. **Find the remaining 0.2 to 0.5 matrix.** After both levers the peak is still above one matrix. I did not attribute it.

Options I did not test, in case they are cheaper than disk: holding the residual copy in single precision (half a matrix, no I/O), or checking residuals on a sample of rows.

## What this does not establish

- Disk speed dependence. A slow or network temporary directory (HPC scratch) could make the disk lever much more expensive than 4 to 18 percent.
- Windows behaviour, including temporary-file handling.
- Certified and adaptive-mesh workflows, frequency sweeps and batch workers. Every run here is a single survey solve at one frequency.
- Each configuration was run once. Differences below about 10 percent are not reliable.
- The fundamental limit is unchanged. At one matrix, 28,000 unknowns still needs 12 GiB and 50,000 needs 37 GiB, so Compressed remains necessary for large problems.

## Reproduction

```
cd audits/claude-2026-11-11/dense-memory-study
ROOT=<checkout of d162169>
# one profiled solve
python profile_dense.py $ROOT '{"body":"pec","n":8000}'
python profile_dense.py $ROOT '{"body":"pec","n":8000,"storage":"disk"}'
# lean: disk residual, budget that forbids pairing
python profile_dense.py $ROOT '{"body":"pec","n":8000,"storage":"disk","options":{"ram_budget_gib":3.0}}'
python run_storage.py $ROOT storage.jsonl    # 24 runs: memory / disk / auto
python run_budget.py  $ROOT budget.jsonl     # 41 runs: Dense and Automatic under tightening budgets
```

`profile_dense.py` prints one JSON line: wall time, baseline and peak memory, the event before the peak, whether pairing was used, the residual storage of each factor, the backend, and a timeline of factor events. `lean.jsonl` and `ff.jsonl` hold the lean runs and the full-field comparisons.
