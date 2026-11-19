# Review of Codex's Dense review response (commit 6b25f9f)

Reviewed: `audits/codex-2026-11-18/dense-review-response/REVIEW_AND_HANDOFF.md`
on `codex/dense-review-response-2026-11-18`.
That branch's production tree equals `main` (`bf5201c`); the Dense change
`5542cd5` is withdrawn. I changed no production file.

`INDEPENDENT_CHECK_PLAN.md` was written after reading only Codex's report,
with a stated hypothesis and the controls that would refute it.

## Summary

1. **Agreed: `5542cd5` stays withdrawn and `main` stays as it is.**
2. **The cause of the four-thread penalty is now identified by a controlled
   test.** NumPy and SciPy each load their own OpenBLAS with its own thread
   pool. Alternating calls between the two pools is about four times slower
   than staying in either one, in both directions. It is not specific to the
   withdrawn change.
3. **Current `main` already pays this cost.** Its Dense solve does the LU in
   SciPy's pool and the residual in NumPy's. With both pools at four threads
   that sequence runs about twice as slow as the same work kept in one pool.
4. **In the real solver on this host, direct SciPy BLAS is clearly faster at
   four threads** (solve stage 2.56 → 1.34 s, four runs each, no overlap) and
   modestly faster at one and two. Codex measured the opposite at four threads
   on its host in three of four pairs. So I agree it is not ready for `main`:
   the result is still host-dependent.
5. **Operator storage, separated as Codex asked:** dense far blocks are at
   most 3% of the operator. Exact near blocks are 47–64% at 3,000–9,500
   unknowns; low-rank far factors take over as the problem grows (65% at
   19,000 unknowns).

## 1. Corrections to my previous report

| My statement in `df18342` | Correction |
|---|---|
| Direct BLAS is "faster than both ... at every thread count I tried" | Too broad. My own table had it 5–15% behind the NumPy-F form at one and two threads, and behind both at width one. |
| The extra time is "entirely in the residual evaluation" | True of my instrumented solver runs. In the sequence benchmark the penalty inflates the LU solves as well (section 2), as Codex found on its host. |
| "OpenBLAS 0.3.31 (Haswell kernels)" | Read back with GHOST's bundled controller: NumPy's library is 0.3.31 and SciPy's is 0.3.30, both using SkylakeX kernels at run time. "Haswell" came from NumPy's build configuration. |
| `threadpoolctl` "not installed", so pools not read back | The controller is bundled in `ghost_backend.execution.thread_control`. All pool counts below are read back inside the process. |
| Operator "near" storage | That evidence field is near plus dense far. Separated in section 4. |
| Density hashes only | Full densities for the key cases are published this time (section 6). |

## 2. Two pools: a controlled test (fresh benchmark)

`bench/pool_controls.py`. Synthetic 4,146-unknown system, 16 columns. The
"solve" and the "product" are each routed through one library or the other;
to make the comparison symmetric, a solve is also emulated by a multiply with
the explicit inverse, so both steps are the same BLAS routine. Each pool's
thread count is set and read back with the bundled controller. Whole-sequence
seconds, median of six, order alternated.

Both pools at 4 threads:

| Solve via | Product via NumPy (current code) | Product via NumPy, F output (withdrawn change) | Product via SciPy `zgemm` |
|---|---:|---:|---:|
| SciPy LU (what the solver does) | 2.25 | 3.34 | **1.14** |
| SciPy multiply by inverse | 2.63 | 3.37 | **0.77** |
| NumPy multiply by inverse | **0.75** | **0.62** | 2.97 |

- Same pool for both steps: 0.62–1.14 s. Different pools: 2.25–3.37 s. The
  pattern is symmetric: SciPy-then-NumPy and NumPy-then-SciPy are both slow.
- The penalty lands on both steps. With SciPy multiply-by-inverse, the solve
  part alone goes from 0.44 s (same pool) to 1.65–1.81 s (mixed), and the
  product from 0.34 s to 0.82–1.73 s.
- The NumPy F-output form is the fastest of all when the solve is also in
  NumPy's pool (0.62 s). The withdrawn change was not slow in itself; it was
  slow because of where it sat.

Other pool settings (solve via SciPy LU):

| NumPy / SciPy threads | Product via NumPy | NumPy, F output | SciPy `zgemm` |
|---|---:|---:|---:|
| 1 / 1 | 2.75 | 2.31 | 2.42 |
| 2 / 2 | 1.67 | 1.42 | 1.53 |
| 1 / 4 | 2.25 | 1.78 | 1.07 |
| 4 / 1 | 1.70 | 1.55 | 2.40 |

With either pool at one thread there is no cross-pool penalty; times are what
the thread counts alone predict. This matches Codex's 1/4 observation.

What this establishes and what it does not:

- Established on this host: "same pool or different pool" predicts the
  timing, for identical arithmetic. My hypothesis survived the control that
  could have refuted it (the bottom row of the first table).
- Not established: the native mechanism. I did not trace worker threads. Two
  pools of four threads on four cores, each presumably keeping its workers
  active for a while after a call, would produce this; that is an inference.
- Not established: that it is the same on other machines. Codex's host has
  more cores than its quota and a different result.

## 3. Real solver (fresh solves)

Production geometry solver, partial coating TE, 4,146 unknowns, 180 angles.
Three trees: `main`; the withdrawn NumPy-F change; `main` with Codex's
guarded direct-BLAS research file. Fresh processes, order rotated. Both pools
were read back inside the Dense solve and equal the requested thread count in
every run. Dense solve stage, seconds:

| Batch | Threads (both pools) | main | NumPy-F (withdrawn) | Direct BLAS |
|---:|---:|---|---|---|
| 16 | 1 | 3.27, 3.12 | 2.70, 2.70 | 2.91, 2.87 |
| 16 | 2 | 2.01, 2.05 | 1.70, 1.74 | 1.82, 1.80 |
| 16 | 4 | 2.62, 2.51, 2.65, 2.49 | 4.10, 4.29, 3.70, 3.67 | 1.58, 1.34, 1.34, 1.32 |
| 256 | 4 | 0.70, 0.74 | — | 0.48, 0.52 |

Medians against main:

| Batch, threads | NumPy-F | Direct BLAS |
|---|---:|---:|
| 16, 1 thread | −16% | −10% |
| 16, 2 threads | −15% | −11% |
| 16, 4 threads | **+52%** | **−48%** |
| 256, 4 threads | — | −31% |

- My acceptance test is met on this host: every direct-BLAS run is faster
  than every main run at four threads, and there is no loss at one or two.
- The first run of the suite (main, four threads, 2.62 s) overlapped the last
  seconds of the pool benchmark; it is in line with the other three.
- Refinement: exactly one step per batch in all 28 runs. All gates pass.
- Densities: each tree is deterministic for a given thread count (identical
  hashes across repeats). Direct BLAS differs from main by 6e-17 (batch 16)
  and 8e-17 (batch 256); NumPy-F by 1.7e-15.
- Also visible in these hashes: `main` itself gives different last bits at 1,
  2 and 4 threads (2.4e-14 between 1 and 4). Bitwise output has never been
  independent of thread count either.

Why Codex's host can disagree: its direct-BLAS runs lost at four threads in
three of four pairs. If the penalty there is small to begin with, or other
NumPy-pool work in the solve keeps the pools alternating, the gain would
shrink or reverse. I cannot test that from here. It is a reason to keep the
candidate out of `main`, as Codex decided.

## 4. Operator storage, separated (fresh solves on `main`)

Read from the operator's own arrays. MiB and share of the operator.

| Case | Unknowns | Exact near | Dense far | Low-rank far | Exact sample rows | Operator total | Inverse | Peak GiB |
|---|---:|---|---|---|---|---:|---:|---:|
| PEC circle TE | 3,144 | 23.7 (48%) | 0 | 22.6 (46%) | 3.1 (6%) | 49.7 | 27.7 | 0.260 |
| Partial coating TE | 4,146 | 52.9 (54%) | 0.5 (1%) | 40.2 (41%) | 4.0 (4%) | 98.1 | 43.2 | 0.343 |
| Coated PEC TE | 5,883 | 120.0 (60%) | 1.0 (1%) | 72.6 (36%) | 5.7 (3%) | 199.9 | 82.9 | 0.518 |
| Dielectric star TE | 8,192 | 184.4 (64%) | 0 | 93.6 (33%) | 8.0 (3%) | 286.8 | 119.5 | 0.699 |
| Multilayer TM | 9,478 | 221.6 (47%) | 13.8 (3%) | 230.3 (48%) | 9.3 (2%) | 475.9 | 198.3 | 0.985 |
| Multilayer TM, twice the size | 18,952 | 388.0 (32%) | 0 | 799.5 (65%) | 37.0 (3%) | 1,226.4 | 573.4 | 2.323 |

- Dense far is negligible everywhere (at most 3%), so the combined figure I
  quoted before was essentially exact near storage. Codex's caution was right
  in principle and makes little difference to these numbers.
- Exact near storage is about half the operator at these sizes and grows
  roughly in proportion to the unknowns (221.6 → 388.0 MiB for twice the
  unknowns).
- Low-rank far storage grows faster (230 → 800 MiB), with the maximum rank
  rising from 98 to 137. At scale it is the larger part.
- The last row failed the production condition gate (it is my deliberately
  hard multilayer, doubled). Its storage figures are valid; no solution from
  it is used.
- Implication for the memory work: at 32k and beyond the target is the
  low-rank far field, whose ranks grow with electrical size. Leaf size does
  not address it. Reducing it means a different far-field representation
  (shared or nested bases), which is a project, not a tuning change. I have
  measured nothing in that direction.

## 5. Position

- `5542cd5` withdrawn; `main` unchanged; leaf defaults unchanged. Agreed.
- Direct BLAS stays research-only. On this host it meets every criterion I
  set, on Codex's it does not, and Windows is untested.
- The new and more general fact is the two-pool interaction. It affects
  current `main` at multi-thread settings and is independent of any of the
  candidate changes. I agree with Codex that shared thread-pool limits should
  not be changed casually. The useful next measurement is on the target
  Windows build: read both pools inside a solve, and time the Dense solve
  stage with the pools equal and with one of them limited to one thread. If
  Windows shows the same pattern, the question becomes how the solver should
  divide threads between the two libraries, which is a design decision for
  whoever owns thread policy.

## 6. Disclosures

- One host: four cores. NumPy OpenBLAS 0.3.31, SciPy OpenBLAS 0.3.30, both
  pthreads, SkylakeX kernels.
- Pool benchmark: one process per pool setting, six alternating repetitions.
  Real solver: 2 processes per tree at 1 and 2 threads, 4 at 4 threads, 2 for
  the wide batch. The real-solver suite uses a wrapper that records stage
  times and pool counts without changing behaviour.
- The direct-BLAS tree is `main` with Codex's research file substituted; I
  did not modify it. I read its guards: it takes the BLAS path only for a
  plain F-contiguous complex128 matrix and candidate with more than one
  column, which is what my benchmark favoured.
- I did not replay Codex's archive, rerun its physical suite, or rerun my
  820-case synthetic suite on the direct-BLAS tree; Codex reports the latter
  passing. My correctness evidence for direct BLAS this round is the 12
  physical runs above.
- Operator breakdown: one run per case.
- All processes returned 0 except the doubled multilayer, whose gate failure
  is noted above.
- Published: all JSON records and fields; full densities for main at 4
  threads, direct BLAS at 4 threads and main at 1 thread
  (`densities/`); SHA-256 of the full density of all 28 real-solver runs
  (`density_hashes.json`).

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `bench/pool_controls.py` and five `pools_*.json` records
- `claude_X.json` (real solver), `claude_Y.json` (operator breakdown), logs
- `claude_run_geometry9.py`, `claude_run_geometry10.py`,
  `claude_run_suite_trees.py`, `claude_audit.py`, `claude_builder.py`
- `results/`, `densities/`, `density_hashes.json`
