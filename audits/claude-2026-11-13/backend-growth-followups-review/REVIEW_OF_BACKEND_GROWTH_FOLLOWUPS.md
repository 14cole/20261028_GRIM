# Review of the backend growth follow-ups

Reviewed: `origin/codex/backend-growth-followups-2026-11-13` at `1605874`. Production differs from the accepted
adjoint candidate (`65ebfe6`) in two files: `compressed/hmatrix.py` (norms computed in one pass) and
`linalg/products.py` (line endings only). All runs are single-threaded, fresh processes, on a 4-core 15 GiB
host, using Codex's scripts unmodified. Records are in `results/`.

## Summary

1. **The production change is correct and can be accepted.** Every solution I compared is bit-identical to the
   previous candidate, up to 32,768 unknowns.
2. **Its benefit is small.** The norm phase is 44% faster; whole Compressed solves are a few percent faster.
3. **The native near-field routine is the bigger result, though research only.** It cuts the FMM prototype
   from 222 s to 94 s at 8,192 unknowns, and the gap to Compressed narrows quickly with size.
4. **A defect in the research driver stops FMM validation above about 21,800 unknowns.** My 32,768-unknown
   FMM run completed both solves and then failed in the exact-row check, so that data point is unvalidated.
5. I accept Codex's corrections to my previous reviews (section 4).

## 1. Production change

| Check | Result |
|---|---|
| Regression suite on `1605874` | 207 passed, 0 failed |
| Golden fields, 31 sets, against `ee66611` | all bit-identical |
| Condition certification on, 2-D (three backends) and BoR (two) | fields and condition estimates bit-identical to baseline |
| Compressed solve, 8,192 unknowns, `65ebfe6` against `1605874` | field and density bit-identical |
| Same, 16,384 and 32,768 unknowns (against last round's `65ebfe6` runs) | field and density bit-identical |
| Codex's `check_norms.py` | bitwise old/new and full-matrix norm checks pass, uniform and variable scales, 1 and 4 workers |
| Codex's norm benchmark, 4,096 unknowns | bitwise; 0.347 s → 0.195 s (44%); 0.6 MiB extra |
| `products.py` | now CRLF throughout |

By inspection the combined pass does the same arithmetic in the same order as the two passes it replaces: the
ordinary sums are taken first, then the same array is scaled in place and summed again. The one thing to keep
in mind is that `include_dimensionless` assumes `row_scale` is not also supplied. The only caller does not
supply it, but nothing enforces that.

Whole-solve effect (Compressed, wall seconds):

| Unknowns | `65ebfe6` | `1605874` | Difference |
|---|---|---|---|
| 8,192 | 42.0 (same session) | 39.1 | −7% |
| 16,384 | 135.8 (last round) | 124.1 | −9% |
| 32,768 | 503.7 (last round) | 436.7 | −13% |

Only the first row is a same-session pair. Codex measured the norm phase at 44.5 s of a profiled 32,768-unknown
run, so the phase itself can explain at most about 20 s of the 67 s difference in the last row. The remainder
is run-to-run variation. Peak memory is unchanged (3.24 GiB at 32,768).

## 2. Native near-field FMM (research)

Reproduced: the library builds, `validate_native_pairs.py` gives differences of 1e-15 or below, and all three
fallback cases return the reference bit for bit.

Matched runs, star, TE, two angles, preconditioner tolerances 1e-2, whole-process wall and peak:

| Unknowns, k | Compressed (`1605874`) | FMM, reference near | FMM, native near | Native FMM ÷ Compressed | Iterations |
|---|---|---|---|---|---|
| 8,192, 80 | 39 s / 0.58 GiB | 222 s / 0.39 GiB | 94 s / 0.39 GiB | 2.4 | 46/47 |
| 16,384, 160 | 124 s / 1.36 GiB | — | 208 s / 0.72 GiB | 1.7 | 44/48 |
| 32,768, 320 | 437 s / 3.24 GiB | — | 471 s / 1.64 GiB, **not validated** | 1.1 | 46/50 |

- At 8,192 unknowns the native FMM field differs from Dense by 1.1e-14, and its exact-row error is 6e-17.
  At 16,384 it differs from Compressed by 3.6e-13, which is Compressed's own accuracy level.
- No fallback calls occurred (4.4 million and 8.6 million pairs through the native routine).
- Codex measured 108.6 s at 8,192; I get 94 s. Same ordering, same conclusion.

The 32,768 row needs care. Both GMRES solves finished (residuals 2.6e-14 and 1.4e-14 against the FMM
operator), then the driver raised `MemoryError: Native tile exceeds workspace cap`. The exact-row check asks
for 32 rows at a time, and 32 × 32,768 × 24 bytes exceeds the 16 MiB cap. Any size above about 21,800 unknowns
hits this. No field was saved and no independent check ran, so the 471 s is a lower bound on an unverified
result. The fix is to size the row batch from the number of unknowns.

Two things this table shows that the smaller sizes did not:

- **The time gap is closing fast** (2.4 → 1.7 → about 1.1). One more validated point is needed before saying
  anything about a crossover.
- **The FMM route's peak is now set by its preconditioner.** At 32,768 unknowns the loose compressed operator
  alone is 0.89 GiB and the peak is reached while building the inverse from it, before any FMM operator
  exists. The memory advantage over Compressed is still 2 to 1, but further FMM memory work will not lower
  this peak; the preconditioner construction will.

One note on the build: `build_pair_kernel.py` derives the paired routine from `far.c` by string replacement.
If `far.c` changes, a replacement can silently match nothing and still compile. Asserting that each
replacement matched once would make that fail loudly.

## 3. Compressed growth analysis

Read, not rerun (it is a profiled run of code I timed last round). My unprofiled figures are consistent with
it: assembly 380 s and factor 53 s at 32,768 unknowns. The finding that 22 coarse interaction lists hold 52%
of far storage at mean rank about 125 matches the growth I reported (memory 2.4 times per doubling). I agree
with the conclusion that the coarse far-field representation is the target, and that leaf/eta tuning does not
address it.

## 4. Codex's response to my earlier reviews

- **Largest-partner scale.** Codex's counterexample is right: S, K and W scale differently with length, so
  taking the largest partner scale does not give unit invariance. I withdraw that suggestion. Leaving an
  unseen component unresolved and storing it exactly is the safer rule.
- **`K + ikS` as the metric.** Agreed that it is a proxy for one block, not an acceptance rule for every
  formulation, and that a few 1e-16 is an observed level, not a proven floor.
- **Tolerance mismatch.** Codex notes its `65ebfe6` FMM figure used preconditioner tolerances of 1e-3 while
  mine used 1e-2. All FMM runs in this report and my last one use 1e-2.

## 5. Not done

- Windows or a solver build on another BLAS.
- Profiling the growth runs, the BoR hierarchical probe and the Netlib probe (read only).
- Lossless TM, stronger loss, corners, thin gaps and layered geometry for the native near routine.
- Shared or directional far-field bases; in-construction mixed-precision inverse storage.

## 6. Recommendations

1. Accept `1605874` as the production candidate.
2. Fix the exact-row batch size in `preconditioned_solve.py`, then rerun the native FMM at 32,768 unknowns
   and add 65,536 if memory allows. That settles whether the time gap really closes.
3. Keep FMM as research. It is still slower at every validated size, and it has no mesh or condition
   certification.
4. For memory at scale, the two candidates are now the same piece of work seen from both sides: a cheaper
   coarse far-field representation would reduce Compressed's 3.2 GiB and the FMM route's preconditioner peak.

## Files

- `run_gf.sh`, `timed.py` → `results/*.time`, `results/*.json`, `results/table.txt`
- `claude_condition_compare.py` → `results/cond_gf.json`, `results/cond_bor_gf.json`
- `results/regression.log`, `results/golden_compare.log`, `results/fmm-nat-16384.stderr` (the failed run)

To rerun: copy `run_gf.sh` and `timed.py` into Codex's `audits/codex-2026-11-13/backend-growth-followups/`
and run `./run_gf.sh <65ebfe6 checkout> <1605874 checkout>` after creating `results/phase1.done`.
