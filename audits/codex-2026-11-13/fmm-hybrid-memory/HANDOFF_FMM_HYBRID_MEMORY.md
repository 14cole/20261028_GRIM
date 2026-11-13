# FMM continuation: streamed storage, local compression and native tuning

Research parent: `59cf19aad4fd562610b94e8cfe643a68036cdd18` (`codex/fmm-review-response-2026-11-13`). This branch adds audit scripts and evidence only. Production source, solver options, numerical defaults and native binaries are unchanged.

## Findings

There is still useful RAM work available. Streaming the existing near assembly removes a large construction peak. A local hierarchical hybrid becomes substantially more effective after shared P1 nodal contributions are summed before compression. Native adaptive FMM also offers an occupancy-dependent memory/time tradeoff. None of these measurements establishes a universal whole-solver saving or justifies replacing Dense and Compressed.

The most important unresolved component is a scalable preconditioner. The complete-solve comparisons below deliberately retain the same near ILU, including a separately assembled streamed near matrix for the hybrid. That isolates operator accuracy/convergence but does not deliver a standalone low-memory hybrid solver.

The study completed 48 operator cases and eight two-angle system cases. Seventeen operator cases checked all columns of all four matrices (68 complete-matrix comparisons); the analysis script verified 200 recorded operator/field comparisons. The compact archive retains the worst-entry columns for full-matrix cases and complete physical field arrays, as detailed in the reproduction notes.

## What was built

| Variant | Change |
|---|---|
| `cached` | Unchanged earlier reusable FMM and bulk COO-to-CSR near construction; comparison baseline. |
| `stream` | Assemble final nodal CSR rows in bounded chunks. K' shares K's transpose values instead of keeping a fourth independent CSR matrix. |
| `stream_sym` | Additionally store only the lower triangles of complex-symmetric S/W; apply both directions and subtract the diagonal once. This is transpose symmetry, not Hermitian symmetry. |
| `hybrid` | Keep the original FMM far field and recursively partition its near panel pairs. Exact singular/close blocks remain dense; admissible local blocks use production's sampled cross-approximation routine. This first version stores panel-local endpoint contributions. |
| `hybrid_nodal` | Sum shared-node contributions inside each local block before compression. Queries include only supporting panels in that block. Contributions from different blocks are accumulated when applying the operator. |
| `native_tuned` | Exercise the existing adaptive/wideband FMM2D library's `hfmm2d_ndiv_` interface at occupancies 25/100/400, keeping eps=1e-12 and all near interactions enabled. No new library was compiled. |

The near/far split remains the original panel-pair split, with the same FMM parameters and quadrature. Local admissibility uses endpoint bounding boxes and `max(diameter_a, diameter_b) <= 1.5 * distance`; a terminal cluster contains at most 24 panels. Exact-near blocks are never replaced merely because frequency is small. The initial hybrid used a 1e-11 local target; the principal nodal runs use 1e-13. Failed or uneconomical compression falls back to exact local storage. The research guard caps the shared S/K/W skeleton at half the smaller block dimension before individual recompression; this can be conservative and is an optimization question for review, not evidence that every rejected block lacks useful low rank.

The common scaling case fixes a unit-radius five-lobed star at k=40 and increases panel count. Its boundary is approximately 48.7 wavelengths long: about 10.5 panels per wavelength at 512 panels and 84.1 at 4,096. It intentionally stresses crowded FMM leaves under refinement. The largest savings therefore address fine geometric/mesh refinement; they should not be transferred unchanged to a uniformly sampled large electrical body. It is not a high-frequency size scan, a 3D capacity study or a prediction for a 20-foot layered model on 32 GiB.

## Measured RAM and time

### 2,048 panels, k=40

| Variant | Setup s | Retained MiB | Peak GiB | S ms | W ms |
|---|---:|---:|---:|---:|---:|
| Bulk cached | 65.75 | 151.86 | 0.606 | 14.52 | 46.08 |
| Streamed | 64.94 | 129.59 | 0.258 | 15.94 | 61.28 |
| Streamed + symmetry | 63.48 | 107.43 | 0.221 | 14.16 | 50.44 |
| Panel-local hybrid, 1e-13 | 107.80 | 142.06 | 0.221 | 23.31 | 56.50 |
| Nodal hybrid, 1e-13 | 103.72 | 91.74 | 0.171 | 17.90 | 54.52 |

### 4,096 panels, k=40

| Variant | Setup s | Retained MiB | Peak GiB | S ms | W ms |
|---|---:|---:|---:|---:|---:|
| Streamed | 290.65 | 391.88 | 0.554 | 35.88 | 102.51 |
| Streamed + symmetry | 262.32 | 303.19 | 0.454 | 33.49 | 112.00 |
| Nodal hybrid, 1e-13 | 333.08 | 196.13 | 0.285 | 36.90 | 101.44 |

Streaming reduced the 2k peak by 57.5%. At 4k, the nodal hybrid reduced peak by 48.7% and retained arrays by 50.0% relative to streaming, with 14.6% more setup time. Relative to streamed symmetric storage, its peak reduction was 37.4%.

Peak is process high-water RSS through setup, single-vector timings and a two-RHS application, before dense reference assembly. Retained-array counts exclude Python/allocator overhead. Times are medians of three single-vector applications unless a repeated native run explicitly states otherwise. All numerical timing cases ran serially in fresh processes, with one BLAS/OpenMP thread.

The first panel-local hybrid was not a clear improvement at small sizes. It retained redundant endpoint contributions and performed extra coefficient queries. At 2,048 panels, its 1e-11 target also produced a sampled W-product difference of 1.71e-11 against the standalone reference. Tightening the target and assembling nodal block values before compression materially improved the accuracy/storage result. This is why the first variant is retained as an unsuccessful comparison, not presented as the recommended design.

The nodal hybrid does not yet reduce setup time. At 2,048 panels it queried 1,972,500 panel pairs for a near field containing 1,163,114 distinct pairs; 101.6 of its 103.7 setup seconds were in the coefficient evaluator. At 4,096 panels it queried 5,651,649 pairs for a 4,652,274-pair near field; 327.5 of 333.1 seconds were in that evaluator. Sampling/probing revisits supporting panels. Bounded query reuse and compress-then-fold experiments are concrete next steps; simply moving more orchestration to native code does not address these repeated integrals.

## Accuracy and complete solves

The compression-active 1,536-panel star test checked all four complete matrices. 55.6% of its near panel pairs were represented in accepted low-rank blocks; its largest relative maximum-entry difference was 4.43e-13. The small 512-panel gap, concentric and graded-square nodal cases accepted no low-rank blocks: those tests qualify partition/scatter and inherited integration, not compression of layered geometry.

The 2k/4k nodal cases also retained complete two-vector outputs and 16 exact reference rows for every operator. Against the streamed two-vector outputs over **all output rows**, the largest difference in the 4k nodal case was 1.09e-13.

### Complete discrete TE/TM checks

| Panels / polarization | Stream iterations (0°/47°) | Hybrid iterations | Stream GMRES s | Hybrid GMRES s | Maximum field difference vs dense |
|---|---|---|---:|---:|---:|
| 512 / TE | 152 / 153 | 152 / 153 | 15.35 | 18.12 | 1.26e-13 |
| 512 / TM | 148 / 149 | 148 / 149 | 20.85 | 15.97 | 2.63e-13 |
| 1024 / TE | 152 / 153 | 152 / 153 | 28.41 | 33.83 | 1.93e-13 |
| 1024 / TM | 148 / 209 | 148 / 209 | 31.31 | 38.36 | 2.91e-13 |

All 16 incident-angle solves passed the physical and scaled backward-error checks. The hybrid did not establish an end-to-end speedup here. The table isolates GMRES time; raw records also include operator and preconditioner setup. Hybrid runs additionally construct the same streamed near operator to supply ILU. Setup timings varied across processes, so these small cases do not support a precise general speed percentage.

TE factor storage grew from 8.06 to 28.51 MiB when panels doubled; TM grew from 7.93 to 26.36 MiB. The 47° TM solve grew from 149 to 209 iterations under refinement, identically for both operators. Reported factor sizes are L/U sparse-array payloads, not isolated factorization RSS. This is direct evidence that preconditioner storage and convergence still deserve attention.

### Shared quadrature and far-field limitations

The concentric 0.001-gap case showed a relative maximum-entry W difference of 2.22e-10 against standalone assembly, essentially unchanged by streaming, symmetry or either hybrid. Independent raw-Hankel Gauss integration at orders 256–2048 traced the tested worst entry to the known channel-dependent quadrature stop: standalone S-only assembly differed from GL2048 by 7.42e-11 in absolute W, while joint S/K differed by 8.48e-14. The independent sequence itself varied by about 9.1e-14; this is a numerical convergence check, not an exact analytic bound. Tightening the ordinary dispatcher to 1e-12 produced the joint result at that entry.

The lossy graded-square case retained the inherited K/K′ maximum-entry discrepancy of approximately 5e-12. Its nodal-hybrid matrices agreed with the streamed matrices to about 4.1e-16 or better in the same maximum-entry metric. This does not establish a uniform 1e-12 matrix-entry guarantee. The targeted tree-transition record is `transition-star-1500.json`, with the actual checked entries retained in its arrays.

All reported operator errors have an explicit reference and norm. A relative maximum-entry matrix error, a random-product error, a physical far-field error and a normalized backward error are different quantities. The local compression tolerance is not a whole-operator certificate.

The FMM far evaluator is unchanged. Its previously documented tree-transition sensitivity remains part of the qualification burden; a better near representation does not fix that translation issue. The implementation remains P1-only and does not supply the production inverse/adjoint actions, condition-estimation workflow, memory admission or packaging required for release.

## Native adaptive FMM: memory versus work

### 2k real-k occupancy scan

| Occupancy | Peak GiB | S seconds | W seconds | Largest sampled-product error |
|---:|---:|---:|---:|---:|
| 25 | 0.315 | 0.684 | 1.456 | 1.3e-14 |
| 100 | 0.152 | 1.003 | 1.150 | 1.28e-14 |
| 400 | 0.092 | 3.226 | 4.308 | 5.38e-15 |

### Fresh 4k repeats (one warm-up, five timed calls per operator)

| k | Occupancy | Peak GiB | S median / range s | W median / range s | Median S CPU s | Median W CPU s |
|---|---:|---:|---|---|---:|---:|
| 40-0.8i | 25 | 0.611 | 1.273 / 1.248–1.279 | 3.190 / 2.995–3.427 | 1.270 | 3.188 |
| 40-0.8i | 100 | 0.230 | 1.785 / 1.756–1.875 | 2.185 / 2.159–2.567 | 1.775 | 2.179 |
| 40+0i | 25 | 0.593 | 1.632 / 1.249–1.880 | 3.127 / 2.509–4.048 | 1.629 | 3.120 |
| 40+0i | 100 | 0.214 | 1.672 / 1.655–2.032 | 2.010 / 1.972–2.147 | 1.663 | 2.008 |

The library's default occupancy at eps=1e-12 is 25. Larger leaves reduce tree/workspace storage but perform more direct point interactions. The data support a tradeoff, not a universal faster setting. The original 4k lossy runs had large timing spikes; their raw results are retained, and fresh warm-up/five-repetition runs with CPU timing were added before interpreting speed. The warm real-k/occupancy-25 timings still varied noticeably; the ranges are retained, and small speed differences should not be treated as established gains.

The 2k real-k profile identifies a more specific investigation than tree reuse alone. At occupancy 25, multipole-to-local translation is about 45% of S call time and 54% of W call time. At occupancy 100, direct evaluation rises to about 85% of S and 75% of W. The time outside the eight reported stages includes tree/workspace setup and other work; it is not all removable tree cost.

In pinned FMM2D `src/helmholtz/hfmm2d.f`, the smaller-box path calls `h2dmploc` per list-2 interaction. `src/helmholtz/helmrouts2d.f` allocates temporary arrays and constructs Hankel/phase coefficients within that call. By contrast, the high-frequency path precomputes diagonal shifts per level. Reusing the low-frequency translation coefficients/matrices is worth investigating, with explicit RAM and stability accounting. The measured stage share is an upper bound on the benefit of eliminating that entire stage, not a promised cache speedup; translation application work remains.

## Another substantial candidate: panel moments

The current point adapter stores three complex phase/dipole tables at eight Gauss nodes per panel. At 4k/k=40 these tables occupy 121.50 MiB. Preprojecting source and target plane waves onto the two P1 endpoint functions would store 20.25 MiB for those moments: **one-sixth as much storage for these tables**. Normals are constant on a linear panel, and derivative moments follow from the sum of endpoint moments divided by panel length.

`panel_projection_proof.py` checked the source charge/dipole/derivative and target value/normal-gradient/derivative identities for real k, lossy k and an all-near case; the largest identity difference was 9.01e-16. This is an algebraic/storage feasibility check, **not a new full operator or a measured solver RAM/time saving**. A complete adapter must preserve the translations, signs, panel assignment and all four Galerkin operators. It must construct the moments in bounded tiles rather than allocating the old tables first. The 4k/k=12 all-near case carried 91.5 MiB of these phase tables despite having zero far translations; that fallback can skip unused far-phase storage altogether.

This is a concrete independent implementation task for Claude, alongside the preconditioner investigation. It can be combined with local hierarchical compression.

## What should happen next

1. Review streaming and transpose/symmetric storage for a bounded integration into the research FMM. Add production-quality allocation guards and qualify the quadrature symmetry policy before any release proposal.
2. Continue the nodal hybrid as a memory prototype. Reduce repeated assembly queries and build a preconditioner that does not reconstruct its large uncompressed near matrix.
3. Investigate persistent native wideband plans and reusable low-frequency translations against the hybrid at identical accuracy. Occupancy alone trades memory for work and is not a complete solution.
4. Compare full 1/16/181-angle workflows with production Dense and Compressed, including actual multi-region dielectric/PEC layers, high electrical sizes and final certification checks.

[CLAUDE_TASKS.md](CLAUDE_TASKS.md) separates review of this implementation from specific independent investigations. [REPRODUCTION.md](REPRODUCTION.md) documents commands, evidence scope and measurement limits. `SUMMARY.json` is generated from the retained arrays and raw records.

Recent work is focused on FMM and its local storage, but the wider solver investigation remains open to direct Compressed improvements, selective precision/refinement, disk-backed residual storage and geometry/order adaptation. Keep the existing production engines and a simple Automatic workflow while these research paths are qualified.
