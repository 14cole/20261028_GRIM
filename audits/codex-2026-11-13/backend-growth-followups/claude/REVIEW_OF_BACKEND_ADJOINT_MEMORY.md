# Review of the adjoint-product change and the corrected backend benchmarks

Reviewed: `origin/codex/backend-adjoint-memory-2026-11-13` at `65ebfe6`. Production differs from the last
accepted candidate (`ee66611`, same content as `09fec5b`) in three files: `linalg/products.py` (new),
`compressed/hmatrix.py` and `linalg/hierarchical.py`. All runs here are single-threaded in fresh processes on
a 4-core 15 GiB host. Records are in `results/`.

## Summary

1. **The production change is correct and can be accepted.** The regression suite passes 207 of 207, all 31
   golden field sets are bit-identical to `ee66611`, and fields and condition estimates with certification on
   are bit-identical on every backend I could reach.
2. **Codex's benchmark correction is right, and it also invalidates my last report's timings.** With the
   production kernel path, Compressed takes 45 s at 8,192 unknowns, not 256 s. My statement that the FMM route
   would cross over near 30,000–60,000 unknowns is withdrawn.
3. **On corrected numbers the FMM prototype is 3.8–9 times slower than Compressed**, for 21–47% less peak
   memory. The gap narrows with size but no crossover is in sight in the measured range.
4. **Not done:** Windows or another BLAS, a BoR Dense-hierarchical case, the leaf/eta study and
   in-construction mixed-precision inverse storage.

## 1. Production change

`adjoint_product(a, b)` returns `a.H @ b`. When the factor is larger than the right-hand side plus the result,
it computes `conj(a.T @ conj(b))`, which avoids copying the factor.

| Check | Result |
|---|---|
| Regression suite on `65ebfe6` | 207 passed, 0 failed |
| Golden fields, 31 sets, against `ee66611` | all bit-identical |
| 2-D, condition certification on: PEC pair and dielectric circle × Compressed, Dense hierarchical, Dense | fields and condition estimates bit-identical to baseline |
| BoR PEC and dielectric sphere × Compressed, Dense | fields and condition estimates bit-identical |
| Codex's `check_products.py` | passes (max error 6e-16) |
| My probe, 3,072 combinations of shape, RHS width, dtype and layout | no shape, dtype, aliasing or input-mutation fault |
| Agreement with the old expression, double precision | 2.9e-15 worst |
| Non-finite inputs | same pattern of non-finite outputs |
| Temporary memory, 8,192 × 256 factor, two RHS | 32.0 MiB before, 0.26 MiB after |

Three observations, none blocking:

- **Not bit-identical in general.** 116 of my 3,072 synthetic cases differ from the old expression in the last
  bits, mainly vector right-hand sides and strided or reversed inputs. Every production path I ran was
  bit-identical, so Codex's statement holds for this host; it should not be read as a guarantee.
- **Single precision.** With complex64 or float32 operands the two expressions differ by up to 2e-6, which is
  single-precision rounding. Production uses double here. This matters for the mixed-precision inverse
  experiment, where factors would be complex64.
- **Line endings.** `products.py` is LF-only; the other files in the package are CRLF.

The in-place recursion in `hierarchical.py` is safe by inspection: both products are formed from `b` before
`result` is written, the same order as before.

BoR does not accept `hierarchical` as a factorization (it allows auto, dense, compressed), so I could not run
the BoR Dense-hierarchical case Codex asked for through the public entry point.

Measured benefit, Codex's paired benchmark rerun (4,096 unknowns, two RHS, median of six rounds):

| Operation | Old | New | Reduction | Codex |
|---|---|---|---|---|
| H-matrix adjoint product | 33.8 ms | 25.1 ms | 26% | 31% |
| Refined adjoint inverse | 103.0 ms | 78.7 ms | 24% | 21% |

The gain is real but applies only to adjoint work (condition estimation). It does not change an ordinary solve.

## 2. Benchmark correction

Codex found that last round's `dense_control.py` and `compressed_control.py` ran without the CPU state that
enables the kernel tables and native far assembly. I reran last round with those scripts unchanged, so my
figures had the same fault. Same case (star, 8,192 unknowns, k = 80, TE), whole-process wall time and peak:

| Method | Last round (mine) | Corrected (mine) | Corrected (Codex) |
|---|---|---|---|
| Dense | 217 s / 2.23 GiB | 53 s / 2.15 GiB | 51 s / 2.13 GiB |
| Compressed | 256 s / 0.67 GiB | 45 s / 0.58 GiB | 51 s / 0.56 GiB |
| FMM + loose inverse | 408 s / 0.46 GiB | 238 s / 0.39 GiB | 250 s / 0.38 GiB |

Both corrected drivers report two kernel tables loaded. The corrected Dense solution differs from last
round's by 4.0e-15 in field and 5.4e-14 in density, the same figures Codex reports, so the earlier runs were
numerically valid and only their timing label was wrong.

The FMM row improves less because only its preconditioner operator uses the fast path (154 s → 24 s). Its own
near-field build goes through a Python-level call and still takes 189 s, 79% of the run.

## 3. Corrected scaling at fixed panels per wavelength

| Unknowns, k | Compressed s / GiB | FMM s / GiB | FMM time ratio | FMM memory saving | FMM iterations |
|---|---|---|---|---|---|
| 4,096, 40 | 15 / 0.31 | 138 / 0.24 | 9.0 | 21% | 42/42 |
| 8,192, 80 | 45 / 0.58 | 238 / 0.39 | 5.3 | 33% | 47/48 |
| 16,384, 160 | 136 / 1.36 | 514 / 0.72 | 3.8 | 47% | 44/48 |
| 32,768, 320 | 504 / 3.24 | not run | — | — | — |

- Compressed's time grows 3.0, 3.0 and 3.7 times per doubling; its peak memory 1.9, 2.4 and 2.4 times.
- The FMM route's time grows 1.7 and 2.2 times per doubling and its memory about 1.6–1.8 times.
- The ratio is falling, but from 3.8 at 16,384 unknowns a crossover would be well beyond 100,000 unknowns if
  the trend held. That is an extrapolation, and the FMM figure is a Python prototype against native code.
- Field agreement between FMM and Compressed is 2.8e-13 and 3.6e-13; against Dense at 8,192 unknowns,
  Compressed is 2.5e-13 and FMM 1.2e-14.

What this changes: Compressed's steepening growth (time and memory both above linear at 32,768 unknowns) is
now the more useful thing to work on, which agrees with Codex's recommendation 6. The FMM route's case rests
on memory, not speed.

## 4. Other investigations in the handoff

Read only; nothing rerun.

- **Leaf size and eta.** The reported gains (up to 8% time, 14% storage) come from one or two geometries.
  Agree with keeping defaults until broader cases are run.
- **Reduced-precision inverse factors.** The saving is in retained bytes only; the peak is unchanged because
  the double-precision inverse is built first. Agree it is not yet a capacity gain. Note the single-precision
  point in section 1 if this is pursued.
- **Native Horner rewrites.** Negative result; nothing shipped.

## 5. Recommendations

1. Accept `65ebfe6` as the production candidate. Optionally convert `products.py` to CRLF for consistency.
2. Treat the corrected table as the reference and stop quoting last round's timings, including mine.
3. Keep the FMM work as research aimed at memory. Its next useful step is moving its near-field build onto
   the native path; until then its timings say little about the method.
4. Measure where Compressed's growth comes from between 16,384 and 32,768 unknowns (assembly 117 → 443 s,
   factor 17 → 57 s) before choosing between leaf/eta tuning and mixed-precision factors.
5. Still open from Codex's list: another BLAS or Windows, and a BoR case that reaches the shared hierarchical
   inverse directly.

## Files

- `claude_adjoint_probe.py` → `results/claude_adjoint_probe.json`
- `claude_condition_compare.py` → `results/cond_*.json`
- `run_ctl.sh`, `timed.py` → `results/c-*.json`, `results/c-*.time`, `results/corrected_table.txt`
- `results/regression.log`, `results/golden_compare.log`, `results/physical-product-paired.json`

To rerun the timing cases: copy `run_ctl.sh` and `timed.py` into Codex's
`audits/codex-2026-11-13/backend-optimization/`, set `GRIM_ROOT` to the checkout root, and run `run_ctl.sh`.

