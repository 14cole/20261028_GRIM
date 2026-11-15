# Independent check plan (written before running anything for this round)

Reviewing Codex `79618d5` (`packing-review-response/REVIEW_RESPONSE.md`).
Read so far: the response, its `PLAN.md`, the source of its new `hooks.py`, and
the production `CompressedSystem.build` / `HMatrixSystem`. Not yet opened: its
JSON results or archive.

## A. Bounded conversion guard (Codex item 1)

Own unit tests, written without looking at `check_conversion.py`:
all-zero; all-tiny; tiny among normal; overflow; one lost component; NaN/Inf
source; denormal doubles; an array whose columns span more than float32's
range (so whole columns vanish while the global bound passes); F- and C-order
and non-contiguous inputs (the guard walks `.flat`); empty array.
Acceptance: result is either a finite complex64 array within eps32 x global
component scale, or the original double array; non-finite input raises.
Expected weakness (prediction): the bound is global, so a column or row that
is small relative to the array's maximum can be erased entirely and still
pass. I expect this to be harmless for these factors but will state it.

## B. Admission accounting (Codex item 2)

Reading `build`, my analysis before measuring (multilayer TM, 9,478 unknowns):
- The accounted peak occurs when the root node finishes: finished children
  plus the root's `u12, v12, u21, v21, e1, e2`, all double.
- Codex's hook packs a node only after `build` returns, so the root's six
  double arrays are all charged at once. Prediction from ranks: peak about
  167 MiB against a packed final of 116 MiB.
- A different build order does not help by itself; the root's own arrays do.

Prototype (research hook, production untouched): a "sequential" build that
1. overwrites `u` with `e = child.solve(u)` in place (the production solve
   documents that input and output may alias), so `u` and `e` are never both
   charged;
2. packs each array as soon as nothing later needs it in double, while
   still forming the Woodbury matrix from the double arrays, so the numbers
   are identical to Codex's bounded packing;
3. charges every array at its actual current size. No array is charged at a
   future packed size.

Predictions (to be checked):
- Unpacked sequential: accounted peak equals the final inverse (about
  198 MiB) instead of about 223 MiB.
- Packed sequential: accounted peak about 142 MiB instead of about 167 MiB.
- Densities bit-identical to the corresponding original-order builds.

Measurement: record the high-water of accounted bytes (including the byte
count of each admission check) in uncapped runs; derive each variant's
admission threshold; then confirm each threshold with capped runs just below
and just above. "Admitted" means passing all production gates with the same
inverse size and refinement count as the uncapped run, i.e. not rescued by a
smaller rebuilt inverse. Process peak RSS is recorded separately.
Accept "improvement" only if capped runs confirm the predicted thresholds and
all gates and Dense comparisons are unchanged.

## C. Leaf scaling and refinement count (my own open item, Codex item 5)

Hypothesis from my last report: equilibrating each leaf block before its LU
reduces the raw apply error. Test end to end in the same research builder
(leaf rows and columns scaled by their own maxima; solves adjusted for
normal, transpose and adjoint).
Prediction: refinement steps on the hard cases fall from 9-10. I hold this
loosely: last round leaf scaling removed only about 60% of the raw error.
Reject the idea if refinement steps do not fall.

Cases: multilayer TM (9,478 unknowns), partial TE and TM (4,146), all against
the fresh Dense anchors from my previous review, production gates unchanged.
Not planned: Windows BLAS, 32k repeats, operator profiling.
