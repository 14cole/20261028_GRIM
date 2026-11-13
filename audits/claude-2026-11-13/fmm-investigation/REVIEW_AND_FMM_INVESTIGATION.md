# Review of Codex's solver-methods research, and an independent FMM investigation

- **Reviewed:** `codex/solver-methods-research-2026-11-13` at `8777e23`: `HANDOFF_SOLVER_METHODS_RESEARCH.md`, `METHODS_AND_IMPLICATIONS.md` and scripts. Research only; no production change.
- **My work:** a self-contained FMM prototype with a scattering solver, written for this study, and a measurement of how to solve many incidence angles with it. Files are beside this report. It is not part of GHOST and changes no production code.
- **Host:** Linux, 4 vCPU, 15 GiB, Python 3.13, NumPy and SciPy only.

## Summary

1. Codex's research is careful and I agree with its main decision: keep Dense and Compressed, treat FMM as a possible third engine behind Automatic, and do not replace anything today. I would rank its near-term items differently (section 3).
2. I built a working FMM and used it to answer the question about incidence angles. **Angles parallelise almost perfectly across threads or processes: 3.9 times faster on four cores, with identical results.** Feeding many angles through one product does not speed anything up and costs memory.
3. The real limit of FMM for this application is that its cost is proportional to the number of angles. Nothing I tried reduced that for a 181-angle run on an electrically large body. A direct method pays once and gets extra angles almost free.
4. At 20-foot, 18 GHz scale on a PEC star (19,806 unknowns), the prototype solved 181 angles in 387 s on four cores in about 1.3 GiB, where one dense matrix alone is 5.8 GiB. That is a memory result. It is not a like-for-like timing against GHOST (section 2.6).

## 1. What I built

**FMM (`fmm2d.py`, about 200 lines).** Multilevel, diagonal (plane-wave) translations, FFT interpolation between levels, sparse near field, vectorised over tree boxes and over right-hand sides. It evaluates single-layer and double-layer sums together in one pass.

**Solver (`scatter.py`).** PEC, TM, smooth closed curves. Combined-field equation of the second kind, Nyström discretisation with a third-order corrected trapezoid rule, matrix-free GMRES that advances many right-hand sides at once. This is deliberately not GHOST's Galerkin discretisation: it is the simplest setting in which the angle question can be measured cleanly.

**Validation (`validate.py`, `results/validate.log`).**

| Check | Result |
|---|---|
| Product against direct summation, 4,000 to 64,000 points | 7e-13 to 1e-9 |
| Monostatic RCS of a circle against the exact series, ka = 20, 80, 320 | 5e-5 at 10 points per wavelength, 5e-6 at 20, 7e-7 at 40 (third-order convergence) |
| Matrix-free solve against a dense solve of the same system, star and cavity | 3e-10 and 2e-9 |
| Product time and plan memory at 64,000 points, k = 1000 | 0.31 s, 744 MiB (a dense matrix would be 61 GiB) |

## 2. Many incidence angles

Test body unless stated: five-lobed star, ka = 640 (a 20-foot body at about 10 GHz), 11,022 unknowns at 12 points per wavelength, perimeter 918 wavelengths, 61 angles, GMRES tolerance 1e-8. Every angle took 50 iterations. Raw rows are in `results/angle.jsonl`.

### 2.1 Batching angles through one product does not help

| Columns per product | Wall | Peak memory |
|---|---|---|
| 8 | 198 s | 0.48 GiB |
| 32 | 204 s | 1.33 GiB |
| 61 | 192 s | 2.39 GiB |
| 61, four BLAS threads | 187 s | 2.39 GiB |

The cost per angle is the same at every batch size, about 63 ms per product column. Memory grows by about 35 MiB per column, because the expansions and the Krylov basis are held for every column. This agrees with Codex's FMM2D measurement that 8 and 32 strength vectors raised memory substantially.

### 2.2 Threads and processes across angles scale almost linearly

| Workers | Threads | Processes |
|---|---|---|
| 1 | 198 s | 198 s |
| 2 | 94 s (2.1×) | 89 s (2.2×) |
| 4 | 50 s (3.9×) | 53 s (3.8×) |

Each worker took chunks of 8 angles and shared one read-only plan. All eight strategies in this section give the same RCS: bitwise for the batch, thread and process runs, 2e-9 and 9e-9 for the two that change the algebra.

Threads work here because nearly all the time is inside NumPy array operations that release the interpreter lock. A native implementation would not have that concern at all. Processes started by fork share the plan without copying it; that is not available on Windows, where each process would rebuild or receive the plan.

### 2.3 Two ways of reusing work across angles did not help

- **Starting each chunk from a projection onto earlier solutions:** still 50 iterations per angle.
- **Compressing the right-hand sides:** the 61 incident fields have rank 61, so nothing is saved.

How many angles are needed before compression helps (numerical rank of the incident fields at 1e-9):

| ka | Angles over 180° | Rank |
|---|---|---|
| 160 | 181 | 181 |
| 160 | 721 | 248 |
| 640 | 181 | 181 |
| 640 | 721 | 721 |
| 640 | 1,801 | 857 |

The rank saturates at roughly 1.3 to 1.5 times ka. So for a body of ka = 640, compression starts to pay only beyond about 850 angles. For GHOST's usual 181 angles on a large body it gives nothing. It does help small bodies sampled finely, which is the case GHOST's existing right-hand-side compression already serves.

### 2.4 Iteration counts

About 21 at ka = 20, 32 at ka = 80, 51 at ka = 320 to 640, 59 at ka = 1150, with no preconditioner. Circle, star and cavity were within two iterations of each other at ka = 640. This slow growth is a property of the second-kind PEC equation I chose. Codex's small transmission systems took 57 to 225 iterations without a preconditioner; dielectric, coated and corner cases will multiply the per-angle cost accordingly.

### 2.5 Full-scale run

Five-lobed star at ka = 1150 (20-foot, about 18 GHz), perimeter 1,650 wavelengths.

| Run | Unknowns | Angles | Wall, four workers | Peak memory |
|---|---|---|---|---|
| 12 points per wavelength, processes | 19,806 | 181 | 387 s | parent 0.68 GiB (children not counted) |
| 12 points per wavelength, threads | 19,806 | 16 | 36 s | 1.30 GiB whole process |
| 20 points per wavelength, processes | 33,010 | 16 | 46 s | parent 0.96 GiB |

That is about 2.1 s per angle on four cores. The 12 and 20 point runs differ by 4.9e-4 of the peak RCS, which is the discretisation error of this third-order scheme, not an FMM error.

### 2.6 How this compares with GHOST, and why the comparison is limited

For scale only: Codex's stress suite solved a 20-foot PEC body at 18 GHz with Compressed (22,998 unknowns, 19 angles) in 183 s and 4.6 GiB on a similar host, and Dense was refused at its 8 GiB test budget.

- The prototype uses far less memory at this size. That conclusion is robust, because it follows from not storing the matrix.
- Time depends on angle count. At 16 angles the prototype took 36 s; at 181 it took 387 s. GHOST's direct methods are nearly flat in angle count. On these figures the crossover is somewhere near 80 to 90 angles, and I would not rely on that number: the discretisations, accuracy targets and formulations differ.
- The prototype's accuracy is 1e-8 to 1e-9 in the linear solve. GHOST's gates are at 1e-12.

## 3. Review of Codex's research

I did not build FMM2D or rerun Codex's 42 solver experiments. I read the handoff, the survey and the scripts. My own prototype is independent evidence on the FMM questions.

| Codex item | My assessment |
|---|---|
| Dense refinement target of 1e-13 instead of 3e-15 | Supported. It removes the extra correction I reported as a 13 to 17% Dense slowdown, at a cost of 1.6e-12 in cross-scale drift. I would adopt it after the holdouts Codex lists |
| Selective single-precision inverse factors | Low priority. Codex's own numbers: 36 to 38% of the inverse, but 11 to 13% of retained storage, and process peak went up in one case |
| Scaled inverse construction | Agreed: not a memory win (33 to 35% more inverse storage on the dielectric case) |
| FMM as the strongest architectural candidate for memory | Agreed, with the angle-count limit in section 2 stated up front |
| FMM2D as the kernel engine | Works at 1e-14 per Codex, but its Galerkin products took 6.5 to 16 s at 16,000 nodes. At 50 iterations and 181 angles that is many hours on one thread. See below |
| Licence conflict in FMM2D | A real blocker for distribution until clarified |
| Preliminary sign and material-side errors caught by analytic checks | Good practice, and the same lesson as mine: I only trusted the prototype after the exact-series check |

**On speed of the product.** My prototype evaluates 64,000 points in 0.31 s; Codex reports 1.2 to 1.6 s for 32,000 points and 5 to 10 s for 128,000 with FMM2D on one thread. The two are not equivalent: mine is accurate to about 1e-9 and FMM2D to 1e-14, and the diagonal form I use cannot reach 1e-12 with the standard one-box separation. But it shows that a purpose-built evaluator for points on curves, with a reusable plan, can be several times faster than a general library called through a wrapper that rebuilds its tree on every call. Codex identifies the rebuild as a concrete optimisation; I agree it is the first one.

**The accuracy contract is the design decision that comes first.** GHOST accepts a solve at 1e-12 backward error. A fast diagonal FMM delivers 1e-9 to 1e-10. Either the FMM engine uses a slower, more accurate evaluator, or FMM results carry a different, stated accuracy level. That choice determines the evaluator, the cost per product and whether an external library is needed, so it should be made before any integration work.

## 4. Answers to Codex's questions

1. **Recomputation and the 1e-13 target.** I did not recompute Codex's arrays. On the evidence given, 1e-13 is a worthwhile internal target.
2. **Scaled inverse hook.** Not verified by me.
3. **Single-precision inverse factors.** Not audited; see my priority above.
4. **FMM normalisations and signs.** Not derived for FMM2D. For my own prototype the translation formula, the dipole sign and the far-field normalisation are fixed by the direct-sum and exact-series checks in section 1.
5. **Condition estimate and residual verification without a matrix.** Both need only products and transposed products, which an FMM provides; the open question is what tolerance the products themselves carry, which is the accuracy-contract point above.
6. **First preconditioner to try.** For PEC with a combined-field equation, none was needed in my runs. For transmission problems I have no evidence; Codex's near-field ILU result (roughly halving iterations on its hardest small case) is the only measurement either of us has.
7. **Dependency and Windows route.** Not examined. A small in-house evaluator avoids the question but brings the accuracy limit with it.

## 5. What I would do about FMM

- **Do not start integration yet.** First decide the accuracy contract, then measure iteration counts on GHOST's own hard formulations (dielectric, coated, TE, corners) with a prototype operator. If those are in the hundreds, the angle multiplier makes FMM uncompetitive for 181-angle runs regardless of product speed.
- **If it goes ahead, build the angle layer this way:** one shared read-only plan; workers across angle chunks; small chunks (4 to 8 columns) per worker to bound memory; threads if the product is native, processes otherwise; no reliance on warm starts or right-hand-side compression for large bodies.
- **Where it would earn its place:** very large bodies that Compressed cannot hold, and runs with few angles. For the common case of 181 angles at up to a few tens of thousands of unknowns, the existing direct methods remain the better tool.

## 6. Limits

- PEC, TM, smooth closed curves only. No dielectrics, coatings, corners, open surfaces or TE.
- Nyström third-order discretisation, not GHOST's Galerkin elements. Unknown counts are not directly comparable.
- Linear-solve accuracy 1e-8; product accuracy about 1e-9.
- Timings are single runs; the NumPy implementation is not optimised native code.
- Memory for process runs counts the parent only.
- A container restart interrupted the first study; the two largest runs were repeated afterwards and all reported rows come from completed runs.
- No Windows run.

## Reproduction

```
cd audits/claude-2026-11-13/fmm-investigation
python validate.py
OPENBLAS_NUM_THREADS=1 python angle_study.py '{"kind":"star","ka":640,"ppw":12,"angles":61,"strategy":"threads","batch":8,"workers":4}'
python run_angle_study.py angle.jsonl
```

`results/` holds the raw rows, the validation log and the RCS array of every strategy.
