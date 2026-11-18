# Independent check plan (written before running anything for this round)

Reviewing Codex `5542cd5` on `codex/postmerge-solver-optimization-2026-11-18`:
one production change (14 lines in `linalg/dense.py`) on top of `main` at
`bf5201c`, plus research on smaller Compressed leaves.
Read so far: the production diff and the handoff text, including its summary
tables. Not opened: its scripts, per-run records or archive.

First fact checked from git, before anything else: the four Compressed files
accepted in earlier rounds are byte-identical on `main` to the reviewed
commit `0be5dc3`.

## Notes from reading the diff

The new branch is taken when the stored matrix is a plain F-contiguous NumPy
array and the batch has at most 16 columns. It allocates an F-ordered
complex128 buffer, lets `matmul` write into it, and subtracts the RHS in
place. Otherwise the old expression runs.
Questions the diff alone does not answer:
 (a) Is the product bit-identical to the old expression for every width from
     1 to 16, and for C-ordered, F-ordered and strided candidates? My
     microbenchmark two rounds ago showed multi-column products identical to a
     direct BLAS call, and I did not test this for width 1 separately. After
     the single-column lesson of the inverse layout, I will not assume it.
 (b) If the stored matrix or candidate were not complex128, the old
     expression's result type followed NumPy promotion; the new buffer is
     always complex128. Does any path reach that branch with another dtype?
 (c) Does anything downstream depend on the residual being C-ordered or on
     it not aliasing?

## Hypotheses

H1. Results: the patched tree gives bit-identical solutions to main for every
    batch width, including 1, on well- and badly-conditioned systems. If
    width 1 differs, the difference is at rounding level and I will report it
    as such, not as identity.
H2. Refinement decisions are unchanged: same number of refinement passes and
    same accept/reject outcome on systems built to sit near the backward-error
    threshold.
H3. Dispatch: widths 16 and 17 take different paths; C-ordered matrices,
    disk-backed and custom operators never take the new path.
H4. Speed on this host, real solves, production code on both trees: for
    16-column batches the solve stage is 25-35% shorter (my research-hook
    measurement two rounds ago was 29-33%); 256-column batches are unchanged
    because they run the old expression. With 4 BLAS threads the narrow gain
    persists; I have no prior measurement there.
H5. Memory: no measurable change in process peak.

## Tests

T1 (H1-H3). Own synthetic suite through the real `DenseFactor` of each tree in
separate processes, outputs saved and compared as raw bytes: random
well-conditioned; rows scaled over 12 orders of magnitude; columns likewise;
ill-conditioned (1e10 to 1e13); a matrix perturbed after factorisation is not
possible through the public API, so "near threshold" is produced by
conditioning instead; widths 1, 2, 3, 8, 15, 16, 17, 64; C, F and strided RHS;
real-valued RHS; a zero column; a 1-D vector. Record refinement counters and
any rejection. Also a direct comparison of the two residual expressions on the
same inputs, outside the solver.
T2 (H4, H5). Physical monostatic sweeps on both trees, fresh processes,
alternating order: 4,096 unknowns x 360 angles in 16-column batches (3 pairs),
8,192 unknowns x 180 angles in 16-column batches (2 pairs), one wide-batch
pair, and the 4,096 case with 4 BLAS threads (2 pairs). Densities compared
bitwise.
T3. Smaller leaves, research only, on the layered and junction geometries
Codex did not use: operator bytes, inverse bytes, process peak, corrections,
accuracy against Dense. Prediction: operator payload falls, by an amount that
depends on geometry, and process peak falls by clearly less.

Acceptance of the Dense change: T1 shows no change in any accept/reject
outcome and no difference beyond rounding; T2 shows a narrow-batch solve gain
larger than the spread and no wide-batch change. Windows BLAS cannot be tested
here and stays an explicit open item.
