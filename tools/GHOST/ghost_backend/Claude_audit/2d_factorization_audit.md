# GHOST 2D factorization modes audit (Claude)

Date: 2026-10-29
Sources: `trials/airfoil_matrix_20261027_full/summary.csv` (920 cases), the solver code in this checkout, and, for the 12 ft planner forecasts, `Codex_audit/size_forecasts.json`. No new benchmark runs were made.
Live version with chart: https://claude.ai/artifact/6z93ZzAiNc17FchkStNBKo

## Bottom line

The claim holds, and it is conservative. Across all 920 cases the most dense ever saved over compressed on one solve was **14.5 s**. Over a full 1 to 10 GHz sweep on the adaptive mesh, dense saved **84 s in total** (177 s against 261 s), while using 1.4x to 4.7x the RAM (5.4 GB against 1.2 GB at 10 GHz).

At 12 ft the case for dense disappears. Dense fits the 8 GiB budget only up to about **17,700 unknowns**, which a 12 ft airfoil passes at about **1.3 GHz**. At 10 GHz a 12 ft airfoil needs about 127,000 unknowns: around **410 GiB** and **14 hours** of LU for dense. Compressed is the only path there, but its memory at that size is uncertain (14 GB from the measured trend, 132 GiB from the planner's own forecast), so it does not fit a 16 GB desktop as the code stands.

Recommendation: cut the user-facing modes from five to two. Drop `hierarchical` and `auto` as options, keep `compressed` as the main path, and keep `dense` as a small-problem fast path and the accuracy cross-check. Put upkeep effort into compressed's rank limit, retained-storage cap and memory forecast, which is where 12 ft runs will fail.

## What the five modes are in the code

Only two are distinct algorithms.

| Mode | What runs | Stores full N x N matrix? | Memory wall |
| --- | --- | --- | --- |
| `dense` | LU below 10,000 unknowns; above that it switches to HODLR (`HIERARCHICAL_MIN_UNKNOWNS`, `linalg/hierarchical.py`) | Yes | about 27 bytes x N^2 |
| `hierarchical` | HODLR factor of the assembled dense matrix, at any size | Yes | about 26 bytes x N^2 |
| `auto` | Same as `dense`, plus a GPU switch at a size threshold (`twod/solver.py` ~line 1579) | Yes | same as dense |
| `compressed` | H-matrix assembled from coefficient queries, no full matrix, above 8,192 unknowns (`compressed/hmatrix.py`) | No | about 0.1 GB per 1,000 unknowns measured |
| `adaptive` | Planner choosing dense or compressed from a cost model, timing history and measured crossovers (`execution/selection.py`, `policy.py`, `timing_history.py`, `factor_timing.py`, `linalg/crossover.py`) | Depends | follows its pick |

`hierarchical` cannot reach larger problems than `dense`: it hit memory errors in the same 88 cases. In the trial, `dense` above 10,000 unknowns was already HODLR.

## What the trial data shows

Dense is faster only while the system is small, and then by seconds. It is not really a frequency effect: on the adaptive mesh (all cases under about 11,300 unknowns) dense beats compressed at all ten frequencies. On fixed local and global meshes it only runs up to 5 GHz and loses to compressed from about 9,000 unknowns.

| Mesh | Cases | Dense ran | Dense faster than compressed | Time dense saved per solve | Dense RAM vs compressed |
| --- | --- | --- | --- | --- | --- |
| Adaptive | 60 | 60 | 60 | 2.9 to 14.5 s (median 8.0 s) | 1.4x to 4.7x more |
| Local and global | 120 | 32 | 20 | -11.5 to +5.2 s (median 2.7 s) | 1.8x to 5.2x more |

Adaptive mesh, P3, no grading, solve seconds:

| GHz | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Sweep total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dense | 2.5 | 4.2 | 6.2 | 9.4 | 13.1 | 20.8 | 26.9 | 31.0 | 29.0 | 33.7 | 177 |
| hierarchical | 3.4 | 5.2 | 7.2 | 9.7 | 12.0 | 16.5 | 19.8 | 21.6 | 26.9 | 30.4 | 153 |
| compressed | 5.5 | 8.5 | 13.5 | 17.8 | 23.2 | 30.9 | 34.8 | 36.8 | 42.6 | 47.1 | 261 |

- On fixed meshes compressed was the only mode to finish in 64 cases; nothing finished in 24.
- `hierarchical` beat `dense` in 37 of 60 adaptive cases, from about 6,000 unknowns up.
- `auto` was never the fastest mode in any case.
- `adaptive` usually landed within about 1 s of the faster of dense and compressed; worst miss 12 s.
- The mesh matters more than the factorization: at 10 GHz compressed took 47 s on the adaptive mesh against 109 s on local P1.

Fitted scaling from the trial: dense LU factor time ~N^2.98; compressed solve time ~N^1.4 and peak RSS ~N^1.1 (over 8,000 to 51,000 unknowns).

## A 12 ft airfoil

The trial airfoil is 11.87 in long, so 12 ft is a 12.13x scale. In 2D, unknowns grow with perimeter in wavelengths, so 12 ft at f GHz is roughly the 1 ft airfoil at 12f GHz.

| 12 ft at | Unknowns | Dense RAM | Dense LU time | Compressed time (fit) | Compressed RAM, measured-trend fit | Compressed RAM, planner forecast |
| --- | --- | --- | --- | --- | --- | --- |
| 1 GHz | 13,600 | 4.6 to 5.6 GiB, fits | about 1 min | about 1 min | about 1.4 GB | 3.1 GiB |
| 3 GHz | 38,500 | 38 to 40 GiB | about 23 min | 2.5 to 4.5 min | about 4 GB | 13.6 GiB |
| 5 GHz | 64,000 | 103 GiB | about 1.7 h | 5 to 9 min | about 7 GB | not forecast |
| 10 GHz | 127,000 | 410 to 415 GiB | about 14 h | 13 to 25 min | about 14 GB | 132 GiB |

Unknown counts and dense RAM agree with the planner forecasts in `Codex_audit/size_forecasts.json` (13,618 unknowns at 1 GHz; 415 GiB dense at 10 GHz). The two compressed RAM columns bracket the truth. The fit assumes ranks keep behaving as they did up to 51,000 unknowns. The forecast assumes ranks grow with electrical size, and it ran 1.5x to 3x above the measured RSS in the trial (for example, 3.9 GiB forecast against 1.2 GB measured at 10 GHz adaptive). Either way, the planner will refuse compressed at 12 ft above about 2 GHz on an 8 GiB budget.

## Recommendation

| Mode | Verdict | Why |
| --- | --- | --- |
| `compressed` | Keep; default for large work | Only mode past about 17,700 unknowns; 1.4x to 5.2x less RAM; only 12 ft path above about 1.3 GHz |
| `dense` | Keep, internal or advanced | Fastest below about 6,000 unknowns; only cross-check compressed has (92 agreement passes); `linalg/dense.py` is 330 lines and shared with refined LU and residual spooling |
| `hierarchical` | Remove as a user option | Same memory wall as dense. Its seconds of gain can come from lowering the automatic LU to HODLR switch from 10,000 to about 6,000 unknowns. Keep the HODLR code: BOR and `compressed/hmatrix.py` use it |
| `auto` | Remove | Never fastest; it is dense plus a GPU switch |
| `adaptive` | Keep as the one automatic choice, simplified | A size-and-memory rule (dense below about 6,000 to 8,000 unknowns if it fits, else compressed) would match the trial's choices; the cost model, timing history and crossover files are 826 lines |

Where upkeep should go instead:
1. Compressed hit its own limits in 4 trial cases: "Off-diagonal rank exceeds 133" (6 GHz local and global P1) and "retained-storage cap" (8 GHz local and global P2). These caps will bind more often at 12 ft.
2. Compressed's memory forecast refused 20 cases at 8.2 to 12.8 GiB, while measured RSS on neighbouring cases was 5 to 6 GB. Tightening the forecast would unlock larger runs on the same machine.
3. One case went the other way: 6 GHz P3 with grading peaked at 10.1 to 10.2 GB, above the 8 GiB it was admitted under.

## Caveats

- No trial row has a validated reference: the P3 references failed with memory errors at every frequency except 1 GHz at 30 points per wavelength. Compressed is only checked against dense, and only where dense ran. A 12 ft compressed run would have no cross-check. This is the strongest reason to keep dense, at least on HPC.
- The 12 ft time and RAM figures are extrapolations about 12x past the largest tested electrical size. Only 12 ft runs would settle them.
- Times are single solves at the trial's angle count.
