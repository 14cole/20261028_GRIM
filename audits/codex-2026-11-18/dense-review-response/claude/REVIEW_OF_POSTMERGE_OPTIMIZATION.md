# Review of Codex's post-merge optimization (commit 5542cd5)

Reviewed: `audits/codex-2026-11-18/postmerge-optimization/HANDOFF_POSTMERGE_OPTIMIZATION.md`
and the one production change (14 lines in `tools/GHOST/ghost_backend/linalg/dense.py`)
on `codex/postmerge-solver-optimization-2026-11-18`, against `main` at `bf5201c`.

I changed no production file. `INDEPENDENT_CHECK_PLAN.md` was written after
reading the diff and the handoff text, before opening Codex's scripts or
records. All runs compare the two production trees directly.

## Summary

**I do not recommend merging the Dense change as it stands.** It is correct,
and it is faster at one and two BLAS threads, but on this host it makes
narrow-batch Dense solves markedly slower at four threads. I also found a
formulation that is faster than both the current code and the proposed change
at every thread count I tried.

1. **Main is as reviewed.** The four Compressed files accepted in earlier
   rounds are byte-identical on `main` to the commit both of us reviewed.
2. **Correctness of the Dense change: fine.** No gate outcome, refinement
   count or accuracy changes in 820 synthetic and 24 physical paired solves.
3. **It is not bit-neutral.** Narrow-batch physical solutions change in their
   last digits (up to 2e-14), because every production Dense solve performs
   one refinement step that uses the residual.
4. **Speed at one thread: confirmed.** Solve stage 28–30% shorter for
   16-column batches; wide batches unchanged.
5. **Speed at four threads: a regression here.** On a real 4,146-unknown case
   the solve stage goes from 2.3 s to 3.9 s (+70%), four runs each, no
   overlap. A standalone benchmark with no solver code reproduces it for
   systems of 2,000 to 6,000 unknowns.
6. **Why both of our microbenchmarks missed it.** Timed back to back, the new
   product is faster at four threads. Timed in the order the solver uses it,
   alternating with LU solves, it is three times slower.
7. **A better candidate.** Calling BLAS `zgemm` directly is within 10–20% of
   the proposed change at one and two threads and about twice as fast as the
   current code at four threads, for narrow and wide batches alike.
8. **Smaller leaves:** on layered and junction geometries they give almost no
   operator saving. I agree they should stay research-only.

## Evidence labels

Fresh solve (FS), fresh microbenchmark (FM), fresh unit test (FU), source
inspection (SI).

## 1. State of main (SI)

`hmatrix.py`, `hmatrix_build.py`, `hmatrix_factor.py` and `factor.py` on
`bf5201c` are identical to `0be5dc3`. The proposed commit changes only
`linalg/dense.py`.

## 2. Correctness

### Synthetic suite through the real `DenseFactor` (FU)

`dense_tree_test.py`, each tree in its own process, outputs compared as raw
bytes. Ten matrices of size 160 (well conditioned; rows or columns scaled over
twelve orders; condition 1e6 to 1e15; overall scale 1e-150 and 1e150), stored
in F and C order; widths 1, 2, 3, 8, 15, 16, 17, 64; RHS in F, C, strided,
real-valued, with a zero column, and as a 1-D vector.

| Check | Result |
|---|---|
| Solves per tree | 820, none failed, none rejected |
| Solutions, main vs patched | bit-identical in all 820 |
| Output memory order | same in all 820 |
| C-ordered stored matrix (must not take the new path) | identical, 410 of 410 |
| Recorded `max_backward_error` | differs in 222 of 820 |

The last row is the first sign that the residual itself is not the same
number. The solutions agree because these small systems never refine.

### The two residual expressions are not bit-identical (FM)

Same inputs, old expression against new, no solver:

| Batch width | Same bits |
|---|---|
| 1, 4, 8, 12, 16 | yes, for matrix sizes 160, 1,000 and 4,096 |
| 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15, 17 | no |

On a 4,146-unknown matrix even width 16 differs. The differences are at
rounding level relative to the product, which makes them comparable to the
residual itself, since the residual is what is left after cancellation.

### Physical solves (FS)

Production geometry solver, Dense, 180 angles, one thread, both trees.

| Case | Unknowns | Batch width | Density, main vs patched | Field | Refinement steps per batch, main / patched |
|---|---:|---:|---|---|---|
| Partial coating TE | 4,146 | 256 | bit-identical | bit-identical | 1 / 1 |
| | | 16 | differs, 1.7e-15 | 4.7e-16 | 1 / 1 |
| | | 10 | differs, 1.6e-14 | 9.6e-16 | 1 / 1 |
| | | 3 | differs, 1.9e-14 | 1.1e-15 | 1 / 1 |
| | | 1 | bit-identical | bit-identical | 1 / 1 |
| PEC circle TE | 3,144 | 256 | bit-identical | bit-identical | 1 / 1 |
| | | 16 | bit-identical | bit-identical | 1 / 1 |
| | | 10 | differs, 5.1e-16 | 2.1e-15 | 1 / 1 |
| | | 3 | differs, 5.2e-16 | 2.1e-15 | 1 / 1 |
| | | 1 | bit-identical | bit-identical | 1 / 1 |
| Multilayer TM | 9,478 | 16 | differs, 5.0e-16 | 1.9e-15 | not recorded |
| | | 10 | differs, 5.1e-15 | 4.8e-15 | not recorded |

- Every production Dense batch performs exactly one refinement step, in both
  trees. The equilibrated backward error after it is 1e-17 to 6e-17. The
  correction is computed from the residual, so a residual that differs in its
  last bits moves the solution in its last bits.
- No refinement count, gate outcome or error level changes. My hypothesis H2
  holds. H1 (bit-identical solutions) does not, for narrow batches.
- This is the same kind of effect as the single-column inverse-layout finding
  last week: rounding-level, harmless to accuracy, and worth stating so nobody
  expects identical output files. Codex's handoff says its 53 synthetic
  outputs match and claims no universal bit identity; the physical case is
  where the difference appears.
- Dispatch is as described: widths above 16 and C-ordered matrices run the old
  expression and are bit-identical between trees.

## 3. Speed

### One BLAS thread (FS) — confirms Codex

Star harness, Dense, fresh processes, order alternated. Solve-stage seconds:

| Case | Main | Patched | Solve change | Compute change | Density |
|---|---|---|---:|---:|---|
| 4,096 unknowns, 360 angles, batch 16 | 6.72, 7.17, 7.49 | 5.15, 5.10, 5.24 | −28% | −11% | bit-identical |
| 8,192 unknowns, 180 angles, batch 16 | 14.01, 14.08 | 9.96, 9.69 | −30% | −6.5% | bit-identical |
| 8,192 unknowns, 180 angles, batch 256 | 5.90 | 5.66 | within noise | — | bit-identical |
| Partial coating, 4,146 unknowns, batch 16 (geometry solver) | 2.99, 3.04 | 2.48, 2.57 | −16% | −1% | differs, rounding |

Process peak is unchanged in every pair (0.630 GiB; 2.149–2.150 GiB).

### Four BLAS threads (FS) — a regression on this host

Partial coating TE, 4,146 unknowns, batch 16, production geometry solver with
four threads requested, order patched / main / main / patched, twice:

| Tree | Wall s (4 runs) | Dense solve stage s (4 runs) |
|---|---|---|
| main | 7.98, 7.96, 8.18, 8.23 | 2.31, 2.27, 2.36, 2.24 |
| patched | 9.34, 9.53, 9.65, 9.59 | 3.71, 4.04, 4.01, 3.88 |

- Solve stage +70%, wall +17%, with no overlap between the two sets. An
  earlier set of four runs showed the same (8.2, 8.3 against 9.9, 9.3).
- With batch 256 the two trees are equal (6.2–6.6 s), as expected since that
  width runs the old expression.
- Timing inside the solve shows the two inverse applications cost the same in
  both trees; the extra time is entirely in the residual evaluation.

### Why back-to-back microbenchmarks do not show it (FM)

The same two expressions, synthetic matrix, 16 columns, no solver code.

Timed back to back (`product_threads.py`), new ÷ old:

| Unknowns | 1 thread | 4 threads |
|---:|---:|---:|
| 4,146 | 0.68 | 0.71 |
| 4,096 | 0.51 | 0.57 |
| 8,192 | 0.49 | 0.54 |

Timed in the solver's order, each product following an LU solve
(`interleaved_bench.py`), whole-sequence time, new relative to old:

| Unknowns | 1 thread | 2 threads | 4 threads | Product at 4 threads, old → new |
|---:|---:|---:|---:|---|
| 2,048 | −22% | −13% | **+198%** | 11 → 64 ms |
| 3,144 | | | **+86%** | 24 → 87 ms |
| 4,096 | | −29% | **+39%** | 48 → 124 ms |
| 4,146 | −18% | −17% | **+55%** | 40 → 122 ms |
| 5,000 | | | **+38%** | 56 → 133 ms |
| 6,000 | | | **+19%** | 80 → 140 ms |
| 8,192 | −30% | −25% | −2% | 154 → 153 ms |

- At four threads the new product carries a roughly constant extra 60–90 ms
  per call when it follows an LU solve. I have not traced it inside NumPy or
  OpenBLAS; it looks like an interaction between the thread pool's state after
  the LAPACK solve and the path NumPy takes for an F-ordered output.
- This host has four cores, so four BLAS threads use all of them. Codex's
  host reports a five-thread default pool with a four-CPU quota, a different
  OpenBLAS build (0.3.30 SkylakeX against 0.3.31 Haswell here), and it measured
  a 24% solve gain for its four-thread narrow case. The effect is therefore
  host- and BLAS-dependent, which is exactly the situation in which a default
  should not be changed on one host's evidence.
- Codex's handoff already flags "a small adverse four-thread wide-product
  result" in its microbenchmark and asks for it to be investigated. This is
  the investigation: the adverse case is real, larger than "small" in the
  solver's actual call order, and applies to narrow batches too.

### A formulation that is faster everywhere I measured (FM)

`interleaved_variants.py`, same solver-order sequence, whole-sequence seconds
(product milliseconds in brackets). "Direct BLAS" is
`scipy.linalg.blas.zgemm(1, a, x)` followed by the in-place subtraction.

| Unknowns, width | Threads | Current code | Proposed change | Direct BLAS |
|---|---:|---|---|---|
| 2,048, 16 | 1 | 0.83 (18.5) | 0.65 (11.9) | 0.69 (13.5) |
| 4,146, 16 | 1 | 3.05 (68.0) | 2.49 (46.2) | 2.67 (53.1) |
| 8,192, 16 | 1 | 14.23 (373) | 9.68 (182) | 10.07 (203) |
| 4,146, 16 | 2 | 1.82 (33.6) | 1.51 (23.3) | 1.56 (26.4) |
| 8,192, 16 | 2 | 8.13 (177) | 6.07 (93) | 6.19 (103) |
| 2,048, 16 | 4 | 0.66 (13.4) | 1.47 (15.2) | **0.30 (3.4)** |
| 4,146, 16 | 4 | 2.55 (39.2) | 3.65 (91.2) | **1.22 (14.3)** |
| 8,192, 16 | 4 | 8.51 (156) | 8.21 (153) | **4.59 (53.9)** |
| 4,146, 4 | 4 | 2.14 (31.3) | 3.42 (116) | **1.04 (10.6)** |
| 4,146, 180 | 1 | 15.63 (315) | 15.04 (296) | 15.34 (302) |
| 4,146, 180 | 4 | 7.67 (146) | 8.12 (169) | **4.82 (87.0)** |
| 4,146, 1 | 1 | 1.26 (20.9) | 1.29 (21.2) | 1.49 (30.1) |
| 4,146, 1 | 4 | 0.65 (5.5) | 0.67 (5.6) | 0.76 (8.4) |

- Direct BLAS is 5–15% behind the proposed change at one and two threads and
  far ahead of both at four, including for a 180-column batch, where the
  proposed change does nothing.
- The one place it loses is a single column, where the existing expression is
  best at every thread count.
- Its results are bit-identical to the current code in the same cases where
  the proposed change is (and differ at rounding level in the others).
- This is a benchmark of an expression, not a tested production change. It
  would need the same correctness suite, the copy behaviour of `zgemm` on
  non-F-contiguous or non-complex128 inputs checked, and above all the target
  Windows BLAS. I am offering it as the candidate to evaluate next, not as
  something to merge on my numbers.

## 4. Smaller Compressed leaves on layered geometries (FS)

Production geometry solver on `main`, leaf size divided by the factor shown,
all gates on, against my Dense anchors. MiB except where noted.

| Case | Leaf size | Operator | of which near / far | Inverse | Peak GiB | Wall s | Density vs Dense |
|---|---:|---:|---|---:|---:|---:|---:|
| Multilayer TM, 9,478 unknowns | 223 | 475.9 | 235.4 / 230.3 | 198.3 | 0.985 | 73.7, 75.6 | 5.4e-10 |
| | 111 | 480.7 | 227.4 / 233.9 | 194.1 | 0.985 | 77.7, 80.3 | 2.7e-10 |
| | 55 | 500.0 | 228.1 / 233.9 | 194.8 | 1.007 | 83.7 | 3.1e-10 |
| Partial coating TE, 4,146 | 187 | 98.1 | 53.5 / 40.2 | 43.2 | 0.343 | 18.9 | 5.7e-11 |
| | 93 | 97.3 | 51.2 / 41.6 | 41.6 | 0.334 | 19.2 | 5.3e-11 |
| | 46 | 101.5 | 51.4 / 41.6 | 41.5 | 0.337 | 21.2 | 5.3e-11 |
| Coated PEC TE, 5,883 | 203 | 199.9 | 121.0 / 72.6 | 82.9 | 0.517 | 34.9 | 3.7e-10 |
| | 101 | 188.5 | 103.6 / 78.6 | 78.5 | 0.502 | 34.8 | 3.9e-10 |

- Halving the leaf changes the operator by +1.0%, −0.8% and −5.7% on these
  three, against Codex's −5.5% to −26.8% on single-body shapes. On the
  multilayer the operator grows. Process peak moves by 0 to 3%.
- Condition estimates, correction counts and accuracy are unchanged.
- My prediction (payload falls by a geometry-dependent amount, peak by less)
  was too optimistic for layered cases: here there is essentially nothing to
  gain.
- This supports Codex's decision to keep leaf size research-only, and it
  suggests leaf size is not where the operator's memory will be recovered for
  coated and layered bodies. Half the multilayer operator is near-field
  storage that the leaf size barely touches.

## 5. Other points on Codex's handoff

- Allocation: I agree with its caution. The change adds no matrix copy and
  process peak is unchanged in every pair I ran; I measured no saving and
  claim none.
- I did not unpack or replay Codex's archive this round, and did not run its
  dispatch, worker or product-probe scripts. My conclusions rest on my own
  runs; where they overlap with its tables (one-thread narrow gain, wide
  batches unchanged) they agree.
- Windows BLAS remains untested by both of us. After this round I would treat
  that as a precondition for any change to this expression, not a follow-up.

## 6. Recommendation

1. Do not merge `5542cd5` as is. Its one-thread benefit is real; its
   four-thread behaviour is host-dependent and negative here for the common
   2,000–6,000-unknown range.
2. Evaluate the direct-BLAS form as the replacement candidate, with width 1
   left on the existing expression. Validate it with the solver's own call
   order (not back-to-back timing), at 1, 2, 4 and more threads, on the
   Windows build, before proposing it for main.
3. If a quick, safe step is wanted in the meantime, restricting the proposed
   path to runs with one BLAS thread would keep the measured gain and avoid
   the measured loss. I have not tested that restriction.
4. Keep leaf size unchanged.

## 7. Disclosures

- One host: 4 cores, OpenBLAS 0.3.31 (Haswell kernels). Thread counts are set
  by `OPENBLAS_NUM_THREADS` and, for the geometry solver, by its `threads`
  option; `threadpoolctl` is not installed here, so pool sizes were not read
  back.
- Physical timing: 3 pairs (4,096), 2 pairs (8,192), 1 pair (wide), 4 + 4 runs
  per tree at four threads. Leaf rows are single runs except the repeated
  multilayer pair. Microbenchmarks are medians of 6 to 21 repetitions in
  alternating order.
- The four-thread physical regression is one geometry. The size range comes
  from the synthetic interleaved benchmark.
- Instrumented runs (suites Q, U, V, W) wrap solver functions to record
  refinement steps and stage times; they do not change behaviour. The timing
  table for one thread uses uninstrumented runs.
- The synthetic "near-threshold" cases did not trigger refinement, so
  refinement behaviour is established from the physical runs, where it always
  occurs.
- Every process returned 0. The first set of four-thread runs lacked
  stage timing; I repeated them with it and report both.
- Scripts in this round assert return codes through the suite runner; the
  analysis was done interactively from the saved records, which are all
  published.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `dense_tree_test.py`, `t1/` (records for both trees)
- `bench/`: `product_threads.py`, `interleaved_bench.py`,
  `interleaved_variants.py`, their JSON outputs, `direct_widths.json`
- `claude_P/Q/R/S/U/V/W` suite manifests and logs; runners
  `claude_run_geometry3.py` … `8.py`, `claude_run_star_plain.py`,
  `claude_run_suite_trees.py`
- `results/`: JSON, stderr and fields for every run;
  `array_hashes_first_batch.json`
