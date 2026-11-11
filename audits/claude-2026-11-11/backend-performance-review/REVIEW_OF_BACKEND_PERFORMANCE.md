# Review of Codex's backend performance implementation

- **Reviewed code:** `distribution/grim-performance-2026-11-11` at `49bd93f` (parent `c20b9ed`, 23 files).
- **Reviewed evidence:** `codex/backend-performance-2026-11-11`, `audits/codex-2026-11-11/backend-performance/HANDOFF_FOR_CLAUDE.txt`, and the earlier `codex/backend-refactor-study-review-2026-11-11`.
- **Host:** Linux, 4 vCPU, 15 GiB, Python 3.13. No Windows or SLURM run.

## Verdict

Accept `49bd93f` as the production tree. Every check I ran passed, and my own benchmark reproduces the claimed gains. Two follow-ups remain, neither blocking: explicit Compressed still fails on the bodies that started this work (F1), and two driver comments are stale (F2).

## What I checked

| Check | Result |
|---|---|
| Diff read in full (all 23 files) | No defect found |
| Line endings of the 20 changed source and doc files | Preserved (CRLF files stay CRLF, LF stay LF) |
| Native binaries and C sources | Unchanged |
| Regression suite, 11 scripts | 207 passed, 0 failed (`regression.log`) |
| Reference fields, baseline against new tree | 31 of 31 sets bitwise equal |
| My benchmark, 32 solves on the new tree | Table below (`results5.jsonl`) |
| Automatic under a RAM limit | Selects compressed and uses the H-matrix at 4,000, 5,000, 6,480 and 8,000 unknowns |
| Four solves in one process at once (two H-matrix, two dense, mixed BLAS settings), three rounds | No deadlock, fields identical to sequential runs, BLAS pool limits restored (`concurrent_blas.py`) |
| Selection overhead of Automatic against explicit Dense, 500 to 2,000 unknowns | Not measurable (within run-to-run noise) |

## Benchmark on the new tree

Wall seconds / peak GiB, 181 angles, one frequency, production threading. "Old" columns are from my study on `c20b9ed`.

| Case | Unknowns | New Automatic | Chosen | Old default (compressed) | Old dense |
|---|---|---|---|---|---|
| Dielectric | 2,000 | 2.6 / 0.26 | LU | 11.6 / 0.27 | 2.3 / 0.26 |
| Coated PEC | 3,240 | 5.5 / 0.65 | LU | 28.2 / 0.41 | 5.2 / 0.65 |
| Airfoil 1 GHz, auto mesh | 1,936 | 4.0 / 0.42 | LU | 16.4 / 0.30 | 4.2 / 0.43 |
| Dielectric, auto mesh | 3,000 | 5.7 / 0.44 | LU | 38.0 / 0.37 | 5.7 / 0.43 |
| PEC | 4,000 | 11.0 / 0.94 | LU | 23.1 / 0.55 | 9.6 / 0.95 |
| Coated PEC | 6,480 | 21.3 / 2.14 | LU | failed | 18.5 / 2.11 |
| Airfoil 3 GHz | 8,666 | 34.7 / 3.67 | LU | 63.8 / 0.85 | 31.1 / 3.67 |
| Airfoil 3 GHz, auto mesh | 3,964 | 11.1 / 1.00 | LU | 39.9 / 0.48 | 9.3 / 0.98 |
| Dielectric | 8,000 | 29.7 / 2.19 | LU | 105.3 / 1.34 | 26.4 / 2.18 |
| PEC | 8,000 | 40.5 / 3.21 | LU | failed | 35.1 / 3.20 |
| IBC | 8,000 | 45.3 / 3.29 | LU | failed | 43.2 / 3.22 |
| Coated PEC | 9,720 | 48.3 / 4.54 | LU | 131.6 / 2.49 | 45.6 / 4.54 |
| PEC | 10,000 | 68.9 / 1.23 | H-matrix | 84.2 / 1.33 | 108.2 / 4.95 (HODLR) |
| Dielectric | 12,000 | 58.7 / 1.52 | H-matrix | 85.8 / 1.56 | 131.9 / 4.80 (HODLR) |
| PEC | 14,000 | 103.8 / 1.92 | H-matrix | 118.4 / 1.95 | 160.0 / 9.50 (HODLR) |
| Airfoil 6 GHz | 17,120 | 122.9 / 1.60 | H-matrix | 143.4 / 1.57 | 237.7 / 9.48 (HODLR) |
| Airfoil 10 GHz | 28,466 | 295.2 / 2.75 | H-matrix | 320.4 / 2.85 | did not fit |

Other rows:

- **Explicit Dense** now uses LU above 10,000 unknowns: PEC 10,000 in 58.2 s (was 108.2 s), PEC 14,000 in 126.2 s (was 160.0 s), same memory.
- **H-matrix BLAS change:** explicit Compressed on the 6 GHz airfoil 123.6 s (was 143.4 s), coated 9,720 unknowns 117.0 s (was 131.6 s), PEC 14,000 106.5 s (was 118.4 s). That is 10 to 14 percent, smaller than the 20 to 30 percent I forecast.
- **Automatic with a RAM limit that excludes dense:** PEC 4,000 at 0.8 GiB 17.4 s; PEC 8,000 at 2 GiB 43.9 s; coated 6,480 at 1.6 GiB 56.0 s. All H-matrix. The last two failed outright on the old default.
- **Fields:** where Automatic chose LU the first amplitudes equal the old dense values exactly; H-matrix rows differ by 3e-12 to 3e-8 relative to old dense (largest for the dielectric and coated cases, as before). `case.py` records only the first eight amplitudes; full-field agreement rests on the 31 reference sets and on Codex's archives.

The Automatic rows below 10,000 unknowns run 0 to 15 percent slower than my earlier dense rows. Repeated runs at 500 to 2,000 unknowns show no systematic gap, so I read this as run-to-run variation rather than selection cost.

## Findings

### F1 (medium, not a regression): explicit Compressed still fails at the rank limit

On the new tree, explicit `factorization='compressed'` still stops with `HierarchicalRejected: Off-diagonal rank exceeds 256` on PEC 8,000 and coated 6,480 unknowns. Codex kept the 8,192 threshold for explicit Compressed deliberately. The GUI now labels that choice "Compressed (lower memory)", so a user who picks it to save memory can still hit the failure, and the message advises Dense, which is the opposite of what they asked for. Automatic with a RAM limit solves the same cases through the H-matrix.

Suggested fix, in order of preference: retry with the H-matrix when the tile inverse is rejected; or apply the 1,024 threshold to explicit Compressed as well; or at least change the advice text to mention Automatic.

### F2 (low): stale comments in the two driver templates

`run_local_monostatic.py` and `run_hpc_monostatic.py` now set `FACTORIZATION = "automatic"`, but the next two comment lines still say "Compressed is the lower-memory default; choose dense explicitly to override" and "Dense uses LU / hierarchical internally".

### F3 (note): the 10,000 boundary is slightly early for speed on this host

At exactly 10,000 unknowns Automatic takes the H-matrix (68.9 s, 1.23 GiB) where LU takes 58.2 s (4.88 GiB). By 12,000 the H-matrix is ahead (58.7 s against 67.3 s). The boundary costs about 10 s in a narrow band and saves 3.6 GiB there, so I would leave it. Codex describes it as a starting heuristic, which is accurate.

### F4 (untested): parallel frequency workers that select compressed

I could not construct a sweep on this host where the planner ran workers in parallel and their memory share forced compressed; the planner chose sequential execution each time. Sequential sweeps under a RAM limit selected the H-matrix correctly at every frequency. Reading the code, workers receive the original options including `automatic`, so the policy flag should be set inside them, but that path is not exercised by my tests or, as far as I can see, by Codex's (its sweep test uses 128-panel bodies, which always choose dense).

## On Codex's corrections to my study

Codex's earlier review made these points against my study, and I accept them:

- My R3 (delete the tile regime) was wrong as stated. Thin-layer exclusions, H-matrix rejection fallback and compressed BoR all still need the tile path, and the H-matrix itself uses `linalg/hierarchical.py`. Keeping both was the right call.
- The raw files hold 193 runs, not 196; the three adaptive-selector runs I cited were not archived.
- "20 panels per wavelength" was wrong for the two-body and coated cases (about 10 and 12).
- My benchmark options left compressed storage at 2,048 MiB, which is not the full GUI profile. The same applies to `results5.jsonl` here.
- R5's interpreter-lock explanation remains a hypothesis; Codex's trace shows the H-matrix already reaches the native kernels.

## Not covered

- Windows, SLURM, hosts with more cores.
- BoR performance (unchanged by this work; its HODLR switch is retained).
- Adaptive mesh growth that crosses the 10,000 boundary mid-run.
- Codex's GUI and driver end-to-end checks, which I did not rerun.

## Reproduction

```
cd audits/claude-2026-11-11/backend-performance-review
ROOT=<checkout of 49bd93f>
python matrix5.py $ROOT results5.jsonl
python concurrent_blas.py $ROOT
python sweep_policy.py $ROOT 5000 1.0 1
GHOST_AUDIT_ROOT=$ROOT OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ../../claude-2026-11-10/regression/run_all.py
python ../../claude-2026-11-10/regression/golden.py $ROOT new.npz   # and the same for c20b9ed, then compare
```
