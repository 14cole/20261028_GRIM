# Review of Codex's stored-basis response check (commit 69ebb27)

Reviewed: `audits/codex-2026-11-15/stored-basis-response-check/REVIEW_RESPONSE.md`
on `codex/stored-basis-response-check-2026-11-15`.
Research only; no production file is changed.

`INDEPENDENT_CHECK_PLAN.md` was written before I ran anything. I had read
Codex's response and the source of its `check_inverse.py`, not its JSON.

Ordering note: Codex's response says I had not reviewed its Dense/Compressed
study (4e0d6e0). That review now exists at
`audits/claude-2026-11-16/dense-compressed-review/` (my commit c6e04a3).

## Summary

1. **Both of Codex's qualifications are correct, and I withdraw two sentences**
   from my previous report:
   - "The whole inverse has gain about 3.5, so the Woodbury corrections cancel
     six orders of magnitude." Wrong: it compared a scaled lower bound with
     unscaled leaf norms.
   - "The leaves are the larger contributor by condition number." Not a valid
     inference from condition numbers.
2. **Measured attribution (new).** Recomputing the apply with selected
   components in extended precision shows the leaf solves are the largest
   single error source: making them alone accurate removes 63–66% of the
   error. The Woodbury solves alone remove 5–6%. Both together remove 87–88%.
3. **The leaf error is a scaling artifact with a cheap remedy (new).** In the
   solver's coordinates the leaf condition numbers are 3.0e3–8.0e3, not
   3.5e6–9.1e6. Row-scaling each leaf before its LU, in ordinary double
   precision, recovers almost all of what extended-precision leaf solves give.
4. Nothing here changes any backend recommendation. The effect is at the
   1e-12 level of the raw inverse apply.

## Evidence labels

Fresh diagnostic (FD): my code, this round. Recorded (RC): read from Codex's
JSON. Algebra (AL): derivation, no measurement.

## 1. Codex's qualifications

One case throughout: dielectric star, 8,192 unknowns, k = 80, loose FMM
preconditioner with tolerances 1e-4, one thread.

| Quantity | Mine (FD) | Codex (RC) |
|---|---:|---:|
| Adjoint inner-product test, relative | 3.6e-12 | 3.75e-12 |
| Scaled gain, lower bound, 20 iterations | 8.406 | 8.417 |
| Scaled gain, lower bound, 30 iterations | 8.432 | — |
| Unscaled gain, lower bound, 20 iterations | 9.418e6 | 9.423e6 |
| Unscaled gain, lower bound, 30 iterations | 9.426e6 | — |
| Leaf cond₁, min / median / max | 3.453e6 / 4.435e6 / 9.139e6 | same to 9 digits |

- My iteration is `M` then `Mᴴ` on an eight-column block, written
  independently; starting vectors differ from Codex's. These are lower bounds,
  as Codex says, still rising slowly at 30 iterations.
- The scaled gain is at least 8.4, not 3.5. My earlier probe iterated `M`
  alone.
- The unscaled inverse has gain of at least 9.4e6, the same size as the leaf
  inverse norms. So there is no six-order cancellation to explain.
- Consequently the ratios 9.3e3 and 1.2e4 in my previous report, which
  normalised by 3.5, are not amplification factors and should be disregarded.

Codex's other remarks I also accept:

- My bitwise replay assertion sampled three blocks, not all. The full-sweep
  evidence that replay and stored Z give the same iteration counts is separate.
- 5,156 counts columns processed (660 block calls), and the 12.6% reduction
  includes the longer restart.

## 2. Is the leaf conditioning a coordinate artifact? (FD)

The tree is built on the physical operator. The solver works in
`R⁻¹ A C⁻¹`, where the row scales `R` span 3.9e-4 to 0.44 and the column
scales `C` span 2.1e-3 to 1.

| Leaf block scaling | cond₁ min / median / max |
|---|---|
| Physical (as factored) | 3.45e6 / 4.44e6 / 9.14e6 |
| Rows only, solver scales | 2.63e4 / 2.85e4 / 3.55e4 |
| Rows and columns, solver scales | 3.01e3 / 5.19e3 / 7.97e3 |
| Rows and columns, each leaf's own maxima | 3.01e3 / 5.19e3 / 7.97e3 |

My prediction was "below 1e4 after scaling": met. About three orders of the
leaf condition number come from mixing rows of very different scale.

(AL) The Woodbury systems `I + V E` are unchanged by diagonal scaling of the
operator, because `V C⁻¹ · C E = V E`. Their condition numbers of up to 9e6 are
therefore not a scaling artifact.

## 3. Which component produces the error? (FD)

`attribution.py` re-implements the apply. A reference is computed with leaf
solves and Woodbury solves refined against an extended-precision residual
(80-bit, ε = 1.1e-19) and the low-rank products done in extended precision.
Each variant makes only the named components accurate. Error is the distance
from the reference in the solver's coordinates, relative to the result. My
all-double variant is bit-identical to the production apply.

| Components made accurate | Random input 1 | Random input 2 | Error removed |
|---|---:|---:|---:|
| none (production apply) | 2.26e-12 | 2.33e-12 | — |
| low-rank products | 2.31e-12 | 2.33e-12 | 0% |
| Woodbury solves | 2.13e-12 | 2.22e-12 | 5–6% |
| leaf solves | 8.29e-13 | 7.97e-13 | 63–66% |
| leaf + products | 8.32e-13 | 7.38e-13 | 63–68% |
| leaf + Woodbury | 2.99e-13 | 2.84e-13 | 87–88% |
| **leaf solves row-scaled, double precision only** | **9.23e-13** | **8.04e-13** | **59–65%** |
| row-scaled leaves + accurate Woodbury | 2.99e-13 | 2.85e-13 | 87–88% |

- No single component meets the 90% criterion I set. The leaves are the
  largest; leaves and Woodbury solves together account for nearly all of it.
- My prediction that the Woodbury solves and products would dominate was
  wrong. Codex was right that condition numbers could not settle this; the
  measurement happens to come out on the side of the leaves.
- The production-apply error of 2.3e-12 agrees in size with the random
  additivity defects both of us measured (3.2e-12 and 3.5e-12).
- **Row-scaling the leaves:** factor `R⁻¹ A_leaf` instead of `A_leaf` and scale
  the right-hand side to match. In plain double precision this gives 9.2e-13
  and 8.0e-13, against 8.3e-13 and 8.0e-13 for extended-precision leaf
  solves. Using each leaf's own row and column maxima instead of the solver's
  scales gives the same.

## 4. What this does and does not establish

- Established for this case: the leaf solves lose accuracy because they are
  factored in badly scaled coordinates, and equilibrating each leaf before its
  LU removes about 60% of the raw apply error at no precision cost.
- Not established: any end-to-end benefit. My diagnostic changes only the
  final leaf solves. In a real build the `e1`, `e2` factors are themselves
  produced by leaf solves and would also change; I did not rebuild the tree.
  The remaining error after fixing the leaves is still 8e-13.
- Not established: that this matters for production Compressed. Codex showed
  the same leaf condition numbers there, and a random-input defect of 5.0e-11.
  Production refines against the operator, so the plausible effect is on
  refinement step counts, not on answers. In my Dense/Compressed review the
  hard multilayer and junction cases needed 9–10 refinement steps against 2–3
  on the star; whether leaf scaling reduces that is the natural next
  measurement and I have not made it.
- One geometry, one size, one tolerance pair, random inputs. The solver's
  actual `VY` input was ten times worse relative to its output last round and
  is not re-measured here.

## 5. Recommended next step

Agreeing with Codex's item 3 (leaf ordering, size and scaling in production
Compressed), and narrowing it: the cheapest experiment is row/column
equilibration of each leaf block before its LU, built into the tree
construction in a research hook, measured on:

1. raw apply error against an extended-precision reference (as here),
2. refinement steps and total solve time for production Compressed on the
   star and on the hard multilayer and junction cases,
3. unchanged accuracy against Dense, storage and construction time.

It should be rejected if refinement steps do not fall. The Woodbury systems
are the remaining source and are not addressed by scaling.

## 6. Disclosures

- The leaf matrices are reconstructed from their LU factors, not reassembled,
  as in Codex's diagnostic. The reference and all variants share that
  reconstruction, so the comparison between variants is consistent, but it is
  not an independent check of the leaf coefficients.
- "Extended precision" is x86 80-bit long double with three refinement steps
  on a double LU. It is about three digits beyond double, enough to serve as a
  reference for errors of 1e-12, not a certified solution.
- Two random inputs, eight columns each. The first run (`attribution.json`)
  had one input and no row-scaled variants; the second (`attribution2.json`)
  added them after I saw the first result. The row-scaling test was therefore
  chosen after seeing that leaves mattered. Shared numbers agree between runs.
- The diagnostic imports Codex's monostatic harness to build the mesh and the
  preconditioner.
- No timing claims. No failed runs.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `attribution.py`, `attribution.json`, `attribution.log`
- `attribution2.py`, `attribution2.json`, `attribution2.log`
