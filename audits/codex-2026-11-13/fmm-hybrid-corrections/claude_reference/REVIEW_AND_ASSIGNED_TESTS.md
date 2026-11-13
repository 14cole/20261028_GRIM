# Review of the FMM hybrid-memory study, and the assigned tests

Reviewed: `origin/codex/fmm-hybrid-memory-2026-11-13` at `bfc5240` (research only; production content is
`09fec5b`, unchanged). Tasks taken from `CLAUDE_TASKS.md` beside the handoff.

Everything here is research code. Nothing in GHOST was changed. Tolerances and quadrature are Codex's defaults
(8-point rule, 10 digits, separation 2, compression target 1e-13, leaf 24, eta 1.5) unless a row says otherwise.
All runs are single-threaded on a 4-core, 15 GiB host. Raw records are in `results/`.

## Summary

1. **One real defect found.** The compressed-near modes (`hybrid`, `hybrid_nodal`) silently return wrong S and W
   on geometry with straight sides. On a 1,400-panel square the S matrix is 12–18% wrong and W 6–21% wrong, with
   no error raised. Cause and a one-line trial repair are in section 2. The streamed modes are not affected.
2. **Everything else I could test holds.** Partition, streamed storage, transpose sharing and symmetric storage
   all check out, including with scrambled node numbering, two loops and concentric contours.
3. **The panel-moment far adapter works.** My independent implementation matches GHOST to 1e-14–1e-13 on all
   four operators, cuts the far tables 5.3× and makes products 1.3–3.7× faster. It supports integration into
   the research operator.
4. **The preconditioner question has a clear answer.** No local preconditioner I tried is worth its memory;
   at k=80 the present near-field ILU gives no reduction at all. A loose *global* compressed factorisation
   brings 150–640 iterations down to 14–34. That is the direction to prototype.
5. **Not done:** the native FMM2D route. This host has no Fortran compiler and no FMM2D build, so the wrapper
   was reviewed by reading only.

## 1. Review items

| Item | Result |
|---|---|
| 1. Partition and nodal aggregation | Holds. Every near panel pair is covered exactly once (count matrix equals the expected matrix) on two loops with scrambled numbering and on concentric contours, at cluster leaf 24 and 5. Full-matrix agreement with GHOST for `hybrid_nodal` on a scrambled 1,536-panel star: 3.5e-13 (real k), 3.9e-13 (k = 40 − 0.8i). |
| 2. Streamed CSR and transpose sharing | Holds. Matrices are bit-identical for row batches 1, 7, 64, 1000 (`stream`) and 5, 64, 1000 (`stream_sym`). Indices are int32. K and K′ share one data buffer. Full matrix against GHOST, scrambled 1,536-panel star: 1.3e-13 worst. |
| 3. Symmetric storage | Holds on the cases tested; see section 3 for what it does not show. |
| 4. Compression error policy | **Defect** on straight sides (section 2). Elsewhere, errors stay at 1e-14–4e-13. |
| 5. Complete-solve interpretation | Agreed, and section 5 strengthens it: the shared near ILU contributes little, so those solves say nothing about a scalable preconditioner. |
| 6. Native tuning wrapper | Read only. The 26-argument order matches the public `hfmm2d_ndiv` source; `idivflag=0` and `ifnear=1` match the library's own defaults; the library's rule gives `ndiv=25` for 0.5e-12 ≤ eps < 0.5e-9, so eps=1e-12 is equivalent. I compared against the current public source, not Codex's pinned build, and ran nothing. |

Two limits met while testing, both Codex's own guards rather than faults:

- A graded square at 400 panels stops with `Panel too long` (longest panel over 0.2 of the leaf side). Severe
  grading at modest panel counts is therefore outside what the prototype accepts.
- On two circles 1e-4 apart, the streamed near field differs from GHOST by 2e-11 (S) and 3.4e-11 (W). This is
  the known thin-gap discrepancy; it is unchanged.

## 2. Defect: straight sides zero out S and W in the compressed modes

**What happens.** `HierarchicalNear` compresses S, K and W of a block with one shared skeleton, scaling each
operator by its sampled norm. Between panels on the same straight side K is exactly zero, so its scale falls to
the 1e-300 floor and its tolerance to about 1e-313. `cross_approximation` then divides zero by that
(`hmatrix.py:450` reports "invalid value encountered in divide") and returns rank 0 for all three operators.
The S and W blocks are stored as zero.

**Evidence** (`square_diag.py`, 1,400-panel square, k=40, full matrices against GHOST):

| Mode | S | K | W |
|---|---|---|---|
| `stream` | 2.2e-14 | 1.3e-13 | 5.1e-14 |
| `hybrid_nodal`, as delivered | 1.8e-1 | 1.3e-13 | 5.8e-2 |
| `hybrid_nodal`, trial repair | 4.0e-14 | 1.3e-13 | 5.1e-14 |

32 of the 92 compressed blocks had rank 0 with 100% error in S and W, and every one had K identically zero.
The same case with scrambled numbering in `review.jsonl` gave 1.2e-1 (S) and 2.1e-1 (W). At 800 panels no
block is compressed, so the fault does not show. That is why Codex's 512-panel checks passed.

**Trial repair.** Give an operator that is zero on the sampled rows the largest scale of the three instead of
1e-300 (one line; shown in `square_diag.py`). With it all 96 compressed blocks are accurate. A sturdier design
would compress each operator with its own stopping test, or leave an identically zero operator out of the
shared pivot search.

**Worth checking in production.** I did not test whether GHOST's own Compressed backend can pass a zero-norm
component to `cross_approximation` in the same way. Its regression cases on squares pass, so I have no evidence
of a problem there, but the routine itself does not guard against it.

## 3. Symmetric storage

| Geometry | Near-field asymmetry, S / W | `stream_sym` vs `stream` | Either vs GHOST |
|---|---|---|---|
| Star, 800 | 3e-16 / 5e-16 | 3e-16 / 5e-16 | 1.1e-14 / 1.4e-14 |
| Concentric, gap 1e-3, 800 | 3e-16 / 6e-16 | same | 4e-14 / 7e-14 |
| Two circles, gap 1e-4, 800 | 3e-15 / 3e-15 | same | 2.0e-11 / 3.4e-11 |
| Graded square, lossy k, 800 | 2e-16 / 2e-15 | same | 4e-14 / 5e-14 |

Keeping one triangle hides nothing material in these cases: the two triangles agree to 3e-15 or better, far
below the 2e-11 thin-gap error. The thin-gap error is symmetric, so it is a quadrature-accuracy question, not
an asymmetry one. I did not design the requested error policy for the assembled operator (including the Maue W
contraction); that task is still open.

## 4. Panel-moment far adapter (independent implementation)

`moment_galerkin.py` uses Codex's tree and translations on one point per panel and stores, per panel, two
source and two target plane-wave moments plus one real table of s·n. The eight-point phase tables are never
allocated; moments are built in tiles of 256 panels. K, K′ and W are obtained from the same moments (normal
factors ±iκ s·n; Maue derivative moments ±(m0+m1)/L). In the all-near fallback no far data is stored.

Validation: complete matrices against GHOST on a 700-panel star, k=40 and k=40−0.8i: S 1.1e-14, K 1.4e-13,
K′ 1.3e-13, W 1.5e-14.

Benchmark against Codex's `stream` mode on the same tree and the same streamed near field (star; fresh process
each; errors are 32 sampled rows against GHOST):

| Panels, k | Mode | Retained MiB | Far tables MiB | Peak GiB | S / K / K′ / W product ms | Worst error |
|---|---|---|---|---|---|---|
| 2,048, 40 | stream | 129.6 | 60.8 | 0.266 | 19.6 / 23.2 / 30.8 / 55.8 | 1.9e-14 |
| | moment | 78.6 | 11.4 | 0.192 | 10.1 / 10.5 / 10.4 / 24.9 | 1.8e-14 |
| 4,096, 40 | stream | 391.9 | 121.5 | 0.585 | 64.4 / 47.0 / 61.0 / 115.0 | 2.2e-14 |
| | moment | 289.9 | 22.8 | 0.442 | 26.0 / 29.3 / 42.6 / 58.1 | 2.1e-14 |
| 2,048, 40−0.8i | stream | 129.6 | 60.8 | 0.277 | 32.4 / 29.0 / 34.1 / 59.1 | 3.0e-14 |
| | moment | 78.6 | 11.4 | 0.204 | 8.7 / 9.8 / 9.3 / 22.1 | 3.0e-14 |
| 2,048, 160 | stream | 79.6 | 62.3 | 0.183 | 24.2 / 28.2 / 33.8 / 76.5 | 2.8e-14 |
| | moment | 27.3 | 11.7 | 0.126 | 18.4 / 16.6 / 23.4 / 51.6 | 2.7e-14 |
| 1,024, 6 (all near) | stream | 77.7 | 16.9 | 0.217 | 7.7 / 8.7 / 9.7 / 16.9 | 2.8e-15 |
| | moment | 60.1 | 0 | 0.195 | 3.6 / 3.4 / 1.7 / 3.6 | 2.8e-15 |

- My `stream` rows reproduce Codex's figures (129.6 and 391.9 MiB retained).
- The far tables shrink 5.3×, not the 6× of the proof script, because I keep the real s·n table.
- Setup time is unchanged (within 3 s); it is dominated by the near-field kernel evaluation in both modes.
- Under mesh refinement at fixed k the near field dominates, so the total saving falls from 39% to 26% between
  2,048 and 4,096 panels. At fixed panels per wavelength (the k=160 row) the far tables dominate and the saving
  is 66%. The adapter complements near-field compression; it does not replace it.

## 5. Preconditioner study

`precond_study.py` assembles GHOST's dielectric transmission system for the star (TE and TM, two incidence
angles), applies Dense's equilibration, and runs GMRES to 1e-12 with each preconditioner. The operator is the
dense matrix, so iteration counts are those an FMM operator accurate to 1e-13 would give. GMRES restart is 400
(Codex's solves used 80; my near-ILU counts of 150/151 TE and 146/148 TM at 512 panels match Codex's 152/148).

Iterations for the first incidence angle; factor size as a fraction of the dense matrix in brackets:

| Case (panels, k, pol., ε) | None | Near ILU sep 2 | Near ILU sep 1 | Band ±32 LU | Leaf block-Jacobi | Schwarz, 1-leaf overlap | Global rank-truncated, 1e-2 | Same, 1e-3 |
|---|---|---|---|---|---|---|---|---|
| 512, 40, TE, 3−0.08i | 240 | 150 (0.50) | 189 (0.22) | 165 (0.31) | 230 (0.04) | 211 (0.60) | 15 (0.23) | 7 (0.31) |
| 512, 40, TM | 187 | 146 (0.49) | 185 (0.22) | 166 (0.31) | 230 (0.04) | 205 (0.60) | 13 (0.24) | 6 (0.32) |
| 1,024, 40, TE | 239 | 150 (0.43) | 191 (0.20) | 190 (0.16) | 234 (0.04) | 212 (0.60) | 16 (0.18) | 7 (0.23) |
| 1,024, 40, TM | 186 | 147 (0.41) | 187 (0.20) | 185 (0.16) | 232 (0.04) | 210 (0.60) | 14 (0.19) | 7 (0.23) |
| 2,048, 40, TE | 237 | 153 (0.36) | 193 (0.16) | 196 (0.08) | 234 (0.04) | 213 (0.60) | 34 (0.16) | 10 (0.18) |
| 1,024, 80, TE | 361 | 367 (0.16) | 396 (0.08) | 354 (0.16) | 430 (0.02) | 400 (0.25) | 16 (0.13) | 8 (0.19) |
| 2,048, 80, TE | 364 | 367 (0.14) | 397 (0.07) | 375 (0.08) | 432 (0.02) | 400 (0.26) | 22 (0.10) | 8 (0.13) |
| 2,048, 80, TM | 298 | 366 (0.14) | 396 (0.08) | 373 (0.08) | 431 (0.02) | 399 (0.26) | 16 (0.10) | 8 (0.13) |
| 1,024, 40, TE, 3−1i | 190 | 136 (0.29) | 172 (0.19) | 168 (0.16) | 220 (0.04) | 207 (0.60) | 14 (0.17) | 7 (0.19) |
| 1,024, 40, TE, 12−0.1i | 632 | 165 (0.28) | 202 (0.17) | 201 (0.15) | 237 (0.04) | 222 (0.60) | 17 (0.19) | 8 (0.23) |

True residuals were 1e-13 to 3e-12 in every row. A few local-preconditioner runs stopped at 1–3e-12, just
short of the target; `results/precond_table.txt` marks them.

What the measurements show:

- **Local preconditioners do not scale.** The present near ILU removes about a third of the iterations at
  k=40 and none at k=80 (TM at k=80 gets worse: 366 against 298). An exact sparse LU of the same near matrix
  gives the same counts, so the limit is the near-field truncation, not the incomplete factorisation.
- **Block-Jacobi and restricted Schwarz on tree leaves are no better than nothing**, and Schwarz with
  two-leaf overlap needs more memory than the dense matrix. A coarse correction was not tried.
- **Global coupling is what matters.** Factorising a copy of the whole system with far blocks truncated to
  relative 1e-2 gives 14–34 iterations in every case, including the high-contrast one where the
  unpreconditioned solve needs 632. At 1e-3 it is 6–10.
- **The near ILU still earns its place for high contrast** (632 → 165), but nowhere else.

Limits of this evidence: the "global rank-truncated" rows use an exact dense LU of the truncated matrix. The
size quoted is the truncated operator's storage, a lower bound; a real compressed factorisation is larger and
has its own construction cost and peak, which I did not measure. Thin layered bodies, complete field errors
and sizes above 4,096 unknowns were not run. The hierarchical approximate inverse was not built.

The obvious candidate already exists: GHOST's Compressed factorisation run at a loose tolerance, used as the
preconditioner for an FMM operator. That reuses qualified code instead of inventing a new factorisation.

## 6. Not done

- **Native adaptive-wideband route** and reproduction of the native stage profiles: no compiler, no library.
- **Reducing hybrid construction queries:** only measured. `hybrid_nodal` queried 1.7–2.1 times the number of
  near pairs (1.82 star, 1.68 square, 2.07 and 2.03 concentric), consistent with Codex's 1.70 at 2,048.
- **Coated-body solves, analytic references, 1/16/181-angle comparisons against Dense and Compressed.**
- **Error policy for the assembled operator** (review item 3).

## 7. Compression active on layered geometry

Concentric contours 1e-3 apart, `hybrid_nodal`, against GHOST:

| Panels | Compressed pair fraction | Rejected blocks | Largest rank | Worst error | Checked |
|---|---|---|---|---|---|
| 1,600 | 0.37 | 120 | 18 | 1.7e-14 | full matrix |
| 2,400 | 0.68 | 46 | 18 | 2.1e-14 | 64 sampled rows |

Compression is active and accurate on this layered case. The 120 rejections at 1,600 panels are the
half-dimension rank cap refusing small blocks; they fall back to dense storage, which costs memory, not
accuracy. These contours are curved, so the straight-side defect does not arise.

## 8. Recommendations

| Direction | Verdict |
|---|---|
| Streamed near field, transpose sharing, symmetric S/W | Sound. Fit for a further prototype. |
| Nodal hierarchical near compression | Fix the zero-operator defect first, then add straight-sided and mixed straight/curved geometry above 1,400 panels to its checks. Not ready for integration. |
| Panel-moment far adapter | Supported by evidence. Fold into the research operator. |
| Near-field ILU as the route to scale | Stop. It does not reduce iterations as electrical size grows. |
| Loose global compressed factorisation as preconditioner | Next bounded prototype: Compressed at 1e-2–1e-3 with an FMM operator, measuring factor bytes, construction peak and iterations at 8,192 unknowns and above, including a thin coating. |
| Native FMM2D route | Undecided; needs a host that can build the library. |

Production integration of any FMM path is not yet supported by this evidence. Dense and Compressed stay.

## Files

- `review_checks.py`, `cases.json`, `run_review.sh` → `results/review.jsonl` (17 cases)
- `square_diag.py` → `results/square_diag_1400.json`, `results/square_diag_1400_fix.json`
- `moment_galerkin.py`, `moment_benchmark.py`, `run_moment.sh` → `results/moment.jsonl`
- `precond_study.py`, `run_precond.sh`, `precond_table.py` → `results/precond.jsonl`, `results/precond_table.txt`
- `fmm_native.py` is a stub standing in for the FMM2D bridge, which cannot load here.

To rerun: copy these scripts beside Codex's in `audits/codex-2026-11-13/fmm-hybrid-memory/`, replace
`fmm_native.py` with the stub, set `GRIM_ROOT` to the checkout root, and run the three `run_*.sh` scripts.
