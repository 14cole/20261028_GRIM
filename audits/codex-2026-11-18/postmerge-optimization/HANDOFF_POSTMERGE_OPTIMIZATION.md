# Post-merge solver optimization: implementation and research handoff

Baseline: `main` at `bf5201c26e0fa3ac98faf6363e52ab9e118d1a7c`. Branch: `codex/postmerge-solver-optimization-2026-11-18`. This branch has one production-file change, in `linalg/dense.py`; it is not merged to main. The earlier inverse-layout review remains closed.

## Decisions

1. Submit the Dense residual-output change for review. For batches of at most 16 RHS, it writes an F-contiguous matrix product directly into an owned F-order residual buffer and subtracts the RHS there. It changes no precision, tolerance, condition estimate, mesh workflow, backend selection, or user option. Disk/custom products retain their implementation; reused inner residuals retain their existing path. It makes no full coefficient copy.
2. Keep smaller spatial leaves research-only. They reduce retained operator bytes in these fixtures but have geometry-dependent time costs; larger-case savings in whole-process RSS are appreciably smaller than operator-payload savings. No default or RAM forecast changes are included.
3. Keep both Dense and Compressed. These results do not establish a catch-all backend, a new FMM advantage, or 32 GB/full-scale-model capability.

## Fresh computation and scope

Codex ran all computations in this handoff: 52 exploratory physical solve processes and three final-source physical checks, each with 180 monostatic angles. Final synthetic checks cover 53 solution cases on each revision plus eight dispatch-boundary checks. The four desktop-worker request-path solves were rerun on the final source. No numerical computation was delegated to Claude. The four worker solves cover PEC and magnetic dielectric examples, both polarizations, Dense/Compressed, and four pre-canceled requests. They are not interactive mid-run GUI cancellation checks.

The performance fixtures are P1 2D cross-sections, not full 3D meshes. Circle/star nominal radius is 1 m (6.56 ft nominal diameter); the star has a 20% five-lobed radius perturbation. The square slot spans 2 m and contains a 0.02 m wide, 1.5 m deep notch. Dielectric permittivity is 3-0.08j, permeability 1, in vacuum; PEC uses zero surface impedance. The leaf scan covers dielectric star TE, slot TM, circle TM, and PEC star TE. Dense timings cover dielectric star TE and slot TM. The scale runs have 4,096 panels / 8,192 dielectric unknowns at k=80 rad/m (about 3.82 GHz); smaller runs use k=40 or 20 (about 1.91 or 0.95 GHz). These are not the requested ultimate 20 ft / 15–18 GHz distribution qualification, and no mesh-convergence certification is claimed.

The host has a 16 GiB cgroup memory ceiling and four CPU-equivalent quota. Physical suites ran sequentially, one fresh process per case; baseline/candidate ordering alternates. Timings are shared-host measurements, not guarantees for another BLAS or Windows. Compute time includes assembly, RHS, factor plus condition checks, solves and fields, excluding independent validation, serialization and Python startup.

## Dense exploratory results and final restriction

The table measures the all-width prototype, preserved as prototype_dense.py. Its narrow path is retained verbatim in the final implementation; its wide path is deliberately not shipped. Entries are medians of four processes per revision at one BLAS thread and three per revision at four BLAS threads. Negative changes mean less time. Raw individual values and paired changes are in `analysis.json`.

| Case | Solve seconds, main → candidate | Solve change | Whole compute change | Peak RSS change |
|---|---:|---:|---:|---:|
| 4,096 unknowns, 16-angle batches, 1 BLAS thread | 4.470 → 2.876 | -35.7% | -4.6% | +0.8% |
| 4,096 unknowns, 180-angle batch, 1 thread | 1.568 → 1.488 | -5.1% | +1.9% | -1.2% |
| 2,048-unknown slot, 16-angle batches, 1 thread | 0.483 → 0.393 | -18.7% | -2.7% | -0.6% |
| 4,096 unknowns, 16-angle batches, 4 threads | 7.482 → 5.697 | -23.9% | -26.5% | -1.0% |
| 4,096 unknowns, 180-angle batch, 4 threads | 0.930 → 1.026 | +10.3% | +7.3% | -1.5% |

The all-width prototype regressed the four-thread 180-angle solve median by about 10.3%, so the final implementation only applies the change at <=16 RHS. Wider batches execute the original expression. Eight explicit dispatch checks cover C/F matrices and widths 1, 16, 17 and 180; three fresh physical solves (narrow, wide one-thread, wide four-thread) validate the final source. The useful gain is concentrated in the solve stage for narrow batches. Assembly and factorization dilute it. Wide batches already reuse the matrix more effectively: do not narrow a sweep to manufacture a percentage speedup. Several paired whole-run comparisons reverse direction, and even unchanged assembly/factor stages drift between processes. Thus whole-run percentage changes, including the favorable four-thread narrow median, must not be attributed wholly to this residual change. This is not a substantial Dense RAM reduction.

The microbenchmark separately randomizes baseline/candidate order for 10 repetitions at widths 1, 16, 180 and 360, with 1 and 4 BLAS threads. It shows layout-sensitive behavior, including a small adverse four-thread wide-product result; it is not substituted for the physical solves. Traced Python/NumPy allocation peaks show reduced overhead, but generally only about 128 KiB for multi-column products in that test, not a guaranteed saved n-by-RHS buffer. NumPy can reuse expression temporaries, and tracemalloc does not measure all native BLAS allocations. The initial plan expected a larger temporary saving; the measured result narrows that claim.

## Compressed leaf experiments

These are explicit research constructor choices. Both operator and inverse leaf size change, so this is not an isolated operator-kernel timing test. “Operator MiB” includes the retained operator accounting; the table compares default with half-sized leaves. Smaller leaves do not change the error targets or arithmetic precision. The exact near/dense-far payload and compressed far payload remain separately recorded in the raw evidence.

| Case | Operator MiB, default → half | Payload change | Peak RSS change | Compute change |
|---|---:|---:|---:|---:|
| star | 128.6 → 116.0 | -9.8% | -9.0% | -13.4% |
| slot | 66.3 → 51.1 | -22.9% | -13.0% | +27.0% |
| pec | 32.9 → 31.1 | -5.5% | -1.9% | -7.6% |
| circle | 110.9 → 81.2 | -26.8% | -10.1% | -13.8% |
| 8,192-unknown star, two processes each | 297.5 → 243.2 | -18.3% | -5.8% | +15.9% |

The four small geometry rows are single-process exploratory measurements; only the larger star was repeated in reversed order. Quarter-sized leaves were also run on all four small geometries; they did not show a general further storage benefit, and often increased runtime. Geometry-dependent dense-far storage and changed inverse trees prevent a simple “halve leaves, halve RAM” rule. At larger sizes, additional sampled leaves can also increase exact-row storage until its cap. A production adaptive policy would need matching admission/forecast changes and representative layered, multi-body and pressure tests. None is silently introduced here.

## Correctness and evidence

All 55 physical cases pass fresh checks on up to 64 independently seeded exact coefficient rows, excluding the operator's retained sampled rows where possible. Largest measured normwise backward error: **1.883e-13** (test limit 1e-12). Largest peak-normalized field difference against the corresponding unchanged/default reference: **1.485e-11** (test limit 1e-8). These are observations, not deterministic error bounds. The production condition and residual gates remain active.

Saved star and slot fields are also compared with numerical Dense references; slot full densities are compared where retained. Synthetic checks cover C/F/strided physical matrices and RHS, vectors, zero RHS, invalid/nonfinite inputs, rejection of injected nonfinite solutions, forced refinement, input preservation, disk restoration, mixed LU, NumPy fallback, a custom product operator, and explicit hierarchical factorization. The final 53 synthetic output arrays match the baseline in this environment; no universal bit-identity claim is made.

All 528 production/resource files were checked against the baseline inventory: only `linalg/dense.py` differs. Existing native binary/source identities are unchanged; no DLL or .so was rebuilt. Complete complex fields for every quoted physical run, sampled residual evidence, raw records and selected full densities are in the hash-verified archive. `README_REPRO.md` identifies exactly which full densities are retained and how to rerun or replay. Shared production quadrature/coefficient routines mean this is algebraic regression validation, not an independent physical reference solution.

## Claude handoff: independent checks first, cross-analysis second

Please write down your own predictions and acceptance criteria before examining the individual timing/array results. Run your own test cases and computations; then cross-analyze our archive and report agreements, discrepancies and the narrowest supported conclusions. Rerunning this exact runner is useful reproduction but is not the entire independent audit.

1. Review the one-file Dense change for ownership, nonfinite behavior, scaled/physical residual gates and all fallbacks. Add independently designed badly scaled and near-threshold cases; check whether F-order output affects refinement decisions rather than assuming bit identity.
2. Measure narrow and wide batches on the target Windows BLAS, including realistic CPU allocations. Is the narrow-batch solve benefit repeatable? Do any wide-batch or BoR workloads regress materially? Investigate the four-thread microbenchmark result before claiming a universal speed improvement.
3. Independently test smaller leaves on layered or multiple-body geometries, then at 32k/64k under constrained memory. Separate operator payload, inverse payload, construction high-water and process RSS. Does any geometry-dependent policy justify its complexity and corresponding memory forecasts?
4. Challenge the allocation interpretation: no full-matrix copy is added, but the microbenchmark does not establish a guaranteed full RHS-buffer saving or whole-process RAM gain. Reproduce with native allocation visibility if making stronger claims.
5. Recommend whether to merge the Dense change alone after review. Keep leaf policy experimental and keep main as the accepted baseline meanwhile. Further high-value work is operator representation/assembly memory and genuine memory-pressure validation, not another unchanged review of the closed inverse-layout issue.

## User-facing consequence

No buttons, profiles, numerical precision settings, accuracy targets, or setup steps change. Dense may finish the solve portion faster when angle batching has at most 16 RHS. Wider batches retain the existing product path. Overall RAM capacity is essentially unchanged by the production candidate. Compressed defaults are unchanged. Windows, full-scale 32 GB behavior and interactive/stalled-native cancellation remain unvalidated by this study.
