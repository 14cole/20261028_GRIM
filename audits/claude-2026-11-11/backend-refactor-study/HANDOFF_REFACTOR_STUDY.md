# GHOST 2D backend: refactor and solver-choice study (handoff for Codex)

- **Tree measured:** production branch `distribution/grim-driver-simplification-2026-11-11` at `c20b9ed`, shipped Linux native kernels.
- **Host:** Linux, 4 vCPU (4 physical), 15 GiB RAM, Python 3.13. No Windows measurement.
- **Scope:** 2D monostatic solver. BOR was not re-measured in this study (see "Not covered").
- **Code changes:** none. Every experiment uses options or environment overrides that already exist, so no experiments branch was needed.
- **Evidence:** `bench/` beside this file (scripts and raw results for 196 timed solves).

## Answers to the questions asked

**Does dense ever save more than a minute?** Yes, on this host with the threading the GUI uses. The largest savings measured at one frequency:

| Case | Unknowns | Dense | Compressed (default) | Dense saves |
|---|---|---|---|---|
| Coated PEC circle | 9,720 | 45.6 s | 131.6 s | 86 s |
| Dielectric circle | 8,000 | 26.4 s | 105.3 s | 79 s |
| Airfoil 3 GHz | 8,666 | 31.1 s | 63.8 s | 33 s |
| Dielectric, automatic mesh workflow | 3,000 | 5.7 s | 38.0 s | 32 s |
| Airfoil 3 GHz, automatic mesh workflow | 3,964 | 9.3 s | 39.9 s | 31 s |

These are per frequency. A sweep multiplies them.

**Is dense only better on small geometries?** No. With four threads, dense LU was faster than compressed in every case up to about 12,000 unknowns, by a factor of 1.8 to 6.7. Compressed wins on time only from roughly 14,000 unknowns, and wins on memory (3 to 6 times less) from about 6,000.

**Should the backend move to compressed only?** No. The evidence points the other way: the GUI already runs compressed only, and that is the slow choice for most problem sizes. It also fails outright on some of them.

## Three findings that drive the recommendations

### F1. The default profile always runs compressed, and compressed does not use the cores

`execution/options.py` `automatic_options()` returns `EFFICIENT_DEFAULTS`, which fixes `factorization='compressed'`. The size-based dense/compressed selection (`factorization='adaptive'`) still exists but the comment at `options.py:596` says it is kept only for explicitly requested legacy profiles.

Thread scaling, PEC circle, 4,000 unknowns, 181 angles (wall seconds):

| Threads (assembly = BLAS) | Dense LU | Compressed, tile | Compressed, H-matrix |
|---|---|---|---|
| 1 | 23.5 | 28.7 | 23.2 |
| 2 | 14.7 | 26.1 | 17.0 |
| 4 | 9.1 | 21.5 | 20.8 |

Dense gains 2.6 times from four threads. Compressed gains 1.1 to 1.3 times while burning 2 to 3 times the CPU. The dielectric circle (4,000 unknowns) shows the same: dense 16.8 → 6.2 s, tile 33.5 → 34.2 s, H-matrix 25.0 → 20.9 s.

My earlier single-thread comparison (dense ahead by 1.0 to 2.0 times) understated the gap for this reason. Those rows are in `bench/results.jsonl` and are superseded by `results3.jsonl`.

### F2. Multi-threaded BLAS makes the H-matrix path slower

Same PEC case, H-matrix, separating the two thread settings:

| Assembly threads | BLAS threads | Wall | CPU |
|---|---|---|---|
| 4 | 1 | 14.8 s | 29.7 s |
| 4 | 4 (`auto`, the default) | 20.8 s | 59.4 s |
| 1 | 4 | 43.9 s | 138.1 s |

Airfoil at 6 GHz (17,120 unknowns): 117 s with BLAS at one thread, 143 s with the default, 227 s with one assembly thread and four BLAS threads. The H-matrix path does many small products, and a four-thread BLAS pool on each costs more than it returns. The stage times show it: `rhs_compression` goes from 1.1 s to 6.6 s when BLAS threads go from 1 to 4.

This is a cheap fix: hold BLAS at one thread inside H-matrix assembly, solve and condition estimation. It is worth about 20 to 30 percent on every large default run.

### F3. Two of the four linear-algebra regimes lose on every measurement

The 2D solver has four regimes: dense LU, dense HODLR (automatic at 10,000 unknowns and above), compressed tile operator (below 8,192 unknowns), compressed H-matrix (above).

**Dense HODLR is slower than plain LU and saves no memory.** `GHOST_HIERARCHICAL_MIN_UNKNOWNS=1000000` forces LU:

| Case | Unknowns | HODLR | Plain LU | Peak memory (both) |
|---|---|---|---|---|
| PEC circle | 10,000 | 108.2 s | 59.5 s | 4.9 GiB |
| Dielectric circle | 12,000 | 131.9 s | 67.3 s | 4.7 GiB |
| PEC circle | 14,000 | 160.0 s | 121.8 s | 9.4 GiB |
| Airfoil 6 GHz | 17,120 | 237.7 s | 184.1 s | 9.5 GiB |

**The tile regime fails on electrically large bodies and is otherwise no faster than the H-matrix.** Three plain bodies stop with `HierarchicalRejected: Off-diagonal rank exceeds 256` after 18 to 31 s, and the message tells the user to choose Dense: coated circle (6,480 unknowns), PEC circle (8,000), IBC circle (8,000). With `GHOST_HMATRIX_MIN_UNKNOWNS=1024` the same three run to completion in 60.9, 51.3 and 58.6 s. Across the other cases the H-matrix is within about 15 percent of the tile regime either way, except the dielectric circle at 8,000 unknowns, where it is 2.7 times faster (39.6 s against 105.3 s).

Fields from the H-matrix agree with dense to between 6e-13 and 1e-8 relative (single-thread comparison; the larger values are the dielectric and coated cases).

## Full table, production threading

Wall seconds / peak process-tree GiB / regime. 181 angles, one frequency, 20 panels per wavelength unless marked "auto mesh" (the certified adaptive workflow).

| Case | Unknowns | Dense | Compressed (default) | Compressed, H-matrix from 1,024 |
|---|---|---|---|---|
| PEC | 500 | 0.8 / 0.15 / LU | 1.4 / 0.14 / tile | 1.8 / 0.14 / tile |
| PEC | 1,000 | 1.5 / 0.20 / LU | 4.4 / 0.17 / tile | 3.1 / 0.18 / tile |
| PEC | 2,000 | 3.1 / 0.34 / LU | 9.5 / 0.27 / tile | 10.7 / 0.27 / H |
| Dielectric | 1,000 | 1.1 / 0.20 / LU | 4.9 / 0.20 / tile | 4.0 / 0.19 / tile |
| Dielectric | 2,000 | 2.3 / 0.26 / LU | 11.6 / 0.27 / tile | 9.8 / 0.32 / H |
| Coated PEC | 1,620 | 2.2 / 0.26 / LU | 10.4 / 0.23 / tile | 10.1 / 0.28 / H |
| Coated PEC | 3,240 | 5.2 / 0.65 / LU | 28.2 / 0.41 / tile | 23.4 / 0.56 / H |
| Airfoil 1 GHz | 2,996 | 5.2 / 0.57 / LU | 17.9 / 0.33 / tile | 16.0 / 0.35 / H |
| IBC | 1,000 | 1.7 / 0.18 / LU | 4.8 / 0.18 / tile | 4.2 / 0.18 / tile |
| Two PEC bodies | 2,000 | 3.1 / 0.33 / LU | 11.6 / 0.28 / tile | 11.8 / 0.30 / H |
| Airfoil 1 GHz, auto mesh | 1,936 | 4.2 / 0.43 / LU | 16.4 / 0.30 / tile | 19.4 / 0.30 / H |
| PEC, auto mesh | 3,000 | 8.6 / 0.61 / LU | 28.1 / 0.38 / tile | 27.5 / 0.35 / H |
| Dielectric, auto mesh | 3,000 | 5.7 / 0.43 / LU | 38.0 / 0.37 / tile | 24.6 / 0.40 / H |
| PEC | 4,000 | 9.6 / 0.95 / LU | 23.1 / 0.55 / tile | 20.3 / 0.47 / H |
| Dielectric | 4,000 | 6.0 / 0.66 / LU | 33.4 / 0.51 / tile | 19.3 / 0.55 / H |
| IBC | 4,000 | 11.0 / 0.94 / LU | 25.1 / 0.54 / tile | 23.7 / 0.48 / H |
| Coated PEC | 6,480 | 18.5 / 2.11 / LU | **failed at 18 s** | 60.9 / 1.37 / H |
| Airfoil 3 GHz | 8,666 | 31.1 / 3.67 / LU | 63.8 / 0.85 / H | 64.5 / 0.83 / H |
| Airfoil 3 GHz, auto mesh | 3,964 | 9.3 / 0.98 / LU | 39.9 / 0.48 / tile | 45.2 / 0.47 / H |
| PEC | 6,000 | 19.4 / 1.90 / LU | 43.1 / 1.59 / tile | 43.4 / 0.68 / H |
| Two PEC bodies | 6,000 | 20.0 / 1.90 / LU | 45.4 / 1.67 / tile | 53.7 / 0.87 / H |
| Dielectric | 8,000 | 26.4 / 2.18 / LU | 105.3 / 1.34 / tile | 39.6 / 1.06 / H |
| PEC | 8,000 | 35.1 / 3.20 / LU | **failed at 27 s** | 51.3 / 1.05 / H |
| IBC | 8,000 | 43.2 / 3.22 / LU | **failed at 31 s** | 58.6 / 1.06 / H |
| Coated PEC | 9,720 | 45.6 / 4.54 / LU | 131.6 / 2.49 / H | 136.1 / 2.54 / H |
| Dielectric | 12,000 | 131.9 / 4.80 / HODLR | 85.8 / 1.56 / H | 87.6 / 1.58 / H |
| PEC | 10,000 | 108.2 / 4.95 / HODLR | 84.2 / 1.33 / H | 86.3 / 1.30 / H |
| Airfoil 6 GHz | 17,120 | 237.7 / 9.48 / HODLR | 143.4 / 1.57 / H | 139.5 / 1.59 / H |
| PEC | 14,000 | 160.0 / 9.50 / HODLR | 118.4 / 1.95 / H | 121.8 / 1.98 / H |
| Airfoil 10 GHz | 28,466 | not run (needs 21.4 GiB) | 320.4 / 2.85 / H | 328.6 / 2.75 / H |

Read the dense column above 10,000 unknowns together with the F3 table: with plain LU those four rows become 59.5, 67.3, 121.8 and 184.1 s.

## Recommended refactors, in order

### R1. One automatic backend: dense LU while it fits, H-matrix above

Replace the fixed `factorization='compressed'` in the automatic profile with a per-mesh rule:

- dense LU when its forecast peak fits the solve's memory budget and the system is below a size threshold;
- H-matrix otherwise.

On this host the time crossover is near 14,000 unknowns (PEC 14,000: LU 121.8 s, H-matrix 118.4 s) and the 15 GiB machine runs out of dense memory near 20,000. The threshold should be derived from memory first; a fixed 12,000 is a reasonable starting value to calibrate.

Expected effect on the cases above: every default run below about 12,000 unknowns becomes 1.8 to 6.7 times faster, and the three failures disappear. The memory cost is real (for example 3.2 GiB against 1.05 GiB at 8,000 unknowns), which is why the rule must be budget-driven.

The existing `factorization='adaptive'` path already does much of this: on PEC 4,000 it chose LU (10.6 s) and on the coated 6,480 case it chose LU (20.6 s). It is not usable as is, because at 14,000 unknowns it chose dense HODLR (156 s, 9.5 GiB) over the H-matrix (118 s, 1.95 GiB). It also carries about 1,000 lines of timing-history and work-prior machinery (`execution/policy.py`, `selection.py`, `timing_history.py`, `factor_timing.py`, `linalg/crossover.py`) that a two-line memory-and-size rule would replace.

Constraints to respect: compressed supports monostatic, double precision only; bistatic already uses dense; the sheet-plus-PEC resonance protection in `formulations/sheet.py` is disabled under compressed.

### R2. Retire the dense HODLR switch

Remove the automatic LU-to-HODLR switch at 10,000 unknowns (`linalg/hierarchical.py` `automatic_hierarchical`, its use in `linalg/dense.py`, `bor/factor.py`, `execution/policy.py`, and the LU/HODLR timing evidence in `factor_timing.py` and `crossover.py`). It was 1.3 to 2.0 times slower than LU at equal memory in all four measurements. With R1 in place, systems that large go to the H-matrix anyway. `linalg/hierarchical.py` is also imported by the tile path, so its removal depends on R3. BOR uses the same switch and needs its own measurement before removal there.

### R3. Retire the tile-operator regime

Lower the H-matrix threshold to the size where R1 hands over from dense, which leaves the tile regime unreachable, then delete it. In a statement-coverage trace of 15 solves (five bodies, three regimes), 770 executed statements ran only in the tile regime, concentrated in `compressed/operator.py`, `tile_processes.py`, `worker_pool.py`, `polarization_cache.py`, `pilots.py`, `block_products.py`, and parts of `inverse.py`, `factor.py` and `memory.py`. That is roughly 1,500 to 2,000 source lines of the 5,862 in `compressed/`, plus the spawn-based worker-process pool. Codex should confirm with its own trace which of these the H-matrix path still imports.

This also removes the rank-256 failure mode and the "choose Dense" advice text, which the default profile gives the user no way to act on.

### R4. Hold BLAS at one thread in the H-matrix path

See F2. Small, independent of R1 to R3, and measurable immediately with `blas_threads=1`.

### R5. Make H-matrix assembly scale with threads

After R1 to R4 the H-matrix serves only large problems, where its assembly dominates (airfoil 6 GHz: 88 of 117 s). Its per-thread `operators` time rises with thread count (PEC 4,000: 14.4 s summed at one thread, 20.8 s at four) while wall time for the stage only halves. That pattern suggests the coefficient evaluation holds the interpreter lock for much of each block. The dense path does not show it, because the native kernel fills whole tiles. Routing H-matrix block evaluation through the same native tile kernel, in larger batches, is the main remaining speed opportunity. I did not profile inside the stage, so treat the cause as a hypothesis.

Multi-region bodies are the worst case for the H-matrix today: coated PEC at 9,720 unknowns takes 131.6 s against 45.6 s dense.

## Not covered

- **BOR.** No new BOR measurements. The earlier audit found near-field operator preparation takes 83 to 94 percent of BOR time, which would make the linear-algebra backend choice secondary there, but that was not re-checked on this tree.
- **Frequency sweeps.** All timings are single-frequency. Per-frequency savings should add, but sweep-level worker scheduling was not measured.
- **Windows and larger hosts.** Thread scaling and the dense/H-matrix crossover depend on core count and RAM. The crossover near 14,000 unknowns is for 4 cores.
- **Accuracy.** Only field agreement between regimes was checked. No regression suite was run, since no code changed.
- **Repeatability.** Each configuration was run once on an otherwise idle host. Differences under about 10 percent should not be relied on.

## Reproduction

```
cd audits/claude-2026-11-11/backend-refactor-study/bench
ROOT=<checkout of c20b9ed>

# one case
python case.py $ROOT '{"body":"pec","n":4000,"backend":"dense","options":{"assembly_threads":"auto","blas_threads":"auto"}}'

python matrix3.py $ROOT results3.jsonl   # production threading, three regimes (89 runs)
python matrix4.py $ROOT results4.jsonl   # thread scaling, BLAS split, LU without HODLR (26 runs)
python matrix.py  $ROOT results.jsonl    # single-thread baseline (62 runs, superseded)
python matrix2.py $ROOT results2.jsonl   # single-thread H-matrix threshold (16 runs)
python trace_cov.py $ROOT && python cov_report.py $ROOT   # needs the coverage package
```

`case.py` runs one solve in a fresh process and reports wall time, parent CPU, peak process-tree RSS, the regime used, stage seconds and the first amplitudes. Spec keys: `body` (pec, ibc, diel, coated, twobody, airfoil), `n` panels on a 1 m circle with frequency set for 20 panels per wavelength, `f` in GHz for the airfoil, `backend`, `options`, `env`, `entry`.

Overrides used: `GHOST_HMATRIX_MIN_UNKNOWNS=1024`, `GHOST_HIERARCHICAL_MIN_UNKNOWNS=1000000`, and the `assembly_threads` / `blas_threads` options.

## Questions for Codex

1. Does the thread-scaling result (F1, F2) reproduce on Windows and on a host with more cores?
2. Is there a reason the automatic profile was fixed to compressed that these measurements miss, such as memory safety on batch nodes?
3. Which `compressed/` modules does the H-matrix path still need once the tile regime is unreachable?
4. Is the BOR HODLR switch any better justified than the 2D one?
