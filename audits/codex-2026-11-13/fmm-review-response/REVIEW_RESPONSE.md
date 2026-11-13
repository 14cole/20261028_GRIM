# Review response: potential savings and the next solver investigations

Reviewed first: Claude's `audits/claude-2026-11-13/fmm-followup-review/REVIEW_OF_FMM_FOLLOWUP.md`, pinned to `68ea134e04f0485b1a3155dff9a84a18b95277e2`; report blob `bb37ba4b7b5b1f51948ebddd70664f97a481b720`. All nine review/evidence files were verified against their Git blob hashes.

## Outcome

Claude's review substantially supports the reusable FMM results. Independent reruns confirm the three difficult complete-matrix comparisons, and confirm that my old 338-second setup measurement should not be used as the representative 4,000-panel cost. The thin-gap discrepancy now has a concrete numerical explanation. The accuracy sensitivity near a tree-depth change remains a real design issue.

Further investigation is worthwhile. The next architectural comparison should be **adaptive wideband FMM versus FMM combined with local hierarchical compression**, with preconditioning included in both. The objective remains lower end-to-end time and peak RAM at qualified physical accuracy, not selecting FMM regardless of results.

No production source, UI setting, numerical default, DLL or .so file is changed. This branch adds research and evidence only, based on `codex/fmm-followup-2026-11-13` at `611f7fa3874cad8d366733e6dbcb38740fab05f0`.

## What was independently rerun

- Fresh native-wrapper 4,000-panel comparison and two fresh reusable-plan runs, with three S/W applications each, process high-water RSS, wall time and child CPU time.
- Complete S, K, K' and W matrices for nearly touching circles (1e-4 gap), the k=65.5 tree-depth transition, and a square with strongly graded corner panels. Every column was applied in bounded batches, not just random test vectors.
- Region-by-region plan inspection for both material wavenumbers at k0=3, 12 and 40.
- Worst-entry near/far decomposition, ordinary near-dispatch tolerance checks, and independent raw-Hankel tensor Gauss integration at orders 256, 512, 1024 and 2048 for the thin-gap discrepancy.
- Two parameter variations on complete columns containing the original worst entries for the transition and graded-square cases. These are targeted diagnostics, not full-matrix qualification of a new default.

The new checks ran with one BLAS/OpenMP thread in the same four-CPU, 16 GiB environment as the earlier work. Claude used another host. The earlier large system, point, angle and phase suites were not all rerun here. The retained arrays and `analyze_review.py` independently recompute the quoted errors.

## Setup timing corrected

Same 4,000-panel, 2 GHz Galerkin star and exact wavenumber as before:

| Run | Setup seconds | Mean S product seconds | Mean W product seconds | Peak before reference GiB |
|---|---:|---:|---:|---:|
| Earlier reusable result | 338.07 | 0.0412 | 0.1203 | 0.953 |
| Claude reusable rerun | 92.85 | 0.0364 | 0.1196 | 0.970 |
| New native-wrapper control | 6.23 | 1.4109 | 2.9295 | 0.334 |
| New reusable run 1 | 100.22 | 0.0451 | 0.1220 | 0.953 |
| New reusable run 2 | 102.63 | 0.0503 | 0.1369 | 0.953 |

The new setup runs were CPU-bound: total child CPU time was approximately equal to wall time. The old 338-second result is preserved, but its cause is not established; I cannot attribute it definitively to host load. It is an outlier relative to these three independent later runs.

Using only this session's native and reusable means, the additional setup amortizes after approximately **70 S products or 34 W products**, replacing the old estimates of 207 and 119. S and W are component operations inside a solve. This arithmetic is not an incident-angle crossover or an end-to-end solver benchmark. The new repeated-product speedups are approximately **30× S and 23× W** on this case.

## Thin-gap mismatch resolved at the tested worst entries

I reproduced Claude's complete-matrix differences exactly: S 2.22e-11 and W 5.41e-11, measured as maximum entry difference divided by maximum reference entry. The worst S and W entries have **zero FMM far-field contribution**. Their differences are entirely in the integrated near blocks.

Both routes already use the production thin-gap handler when its eligibility tests select it. The distinction is that the prototype constructs S and K together, whereas the reference S/W paths request S alone. The adaptive test uses the maximum error of the requested channels. Requesting K as well can trigger additional refinement of the same S integral. The ordinary near tolerance is 1e-9.

At the original worst entries:

| Quantity | Standalone matrix vs independent GL2048 | Joint S/K prototype vs GL2048 | Standalone near dispatcher at rtol=1e-12 vs GL2048 |
|---|---:|---:|---:|
| S absolute difference | 7.86e-16 | 1.27e-18 | 3.60e-19 |
| W absolute difference | 2.23e-11 | 6.25e-14 | 5.02e-14 |

The independent Gauss sequences agree to about 1.4e-18 for the S entry and 6.8e-14 for W across orders 256–2048. That is sufficiently tighter than the original discrepancy to identify the joint S/K result as closer in these checks. The sequence is a numerical convergence check, not an exact analytic error bound. High-order quadrature itself accumulates rounding error.

**Correction to Claude's interpretation:** this is not evidence that the FMM adapter lacks thin-gap handling. It is a channel-dependent quadrature stopping difference in shared assembly machinery. A consistent quadrature accuracy policy still needs qualification before tight whole-operator comparisons and coated-body integration. I have not changed production's tolerance or selected a new global default.

The final diagnostic preserves the dispatcher's eligibility rules. An earlier probe that directly called the semi-analytic integrator on all supporting pairs is retained as `THIN_INITIAL_DIAGNOSTIC.json`; it is superseded by the dispatcher-respecting result above.

## Tree-transition and graded-corner accuracy

The complete-matrix reruns exactly reproduced Claude's maxima:

| Case | Worst relative maximum-entry difference |
|---|---:|
| Star just after the next tree level, k=65.5 | 1.75e-12 |
| Strongly graded square, k=40 | 1.68e-12 |

Unlike the thin-gap result, the worst K/K' discrepancies involve the far-field evaluator. On the retained complete columns containing the original worst entries:

| Configuration | Transition worst checked error | Graded-square worst checked error |
|---|---:|---:|
| Reduce expansion digits from 10 to 8, retain separation 2 | 4.76e-11 | 7.69e-11 |
| Retain 10 digits, widen separation from 2 to 3 | 4.68e-14 | 7.93e-14 |

Reducing order is not a general cure: it made these tests worse. Widening the near field improves these checked columns, but increases the near panel-pair counts from 253,088 to 368,510 (46%) and from 503,888 to 598,200 (19%). The normalization in this parameter test is the maximum reference entry of the checked columns; the original table uses the whole matrix. These are diagnostics of the mechanism, not a universal accuracy guarantee or justification for silently switching the default to separation 3.

A maximum-entry operator difference is also not the solver's normalized backward error. Full-system residual, condition and physical field tests remain necessary. A stable wideband/hybrid implementation should have an explicit accuracy policy across tree-depth transitions, loss, grading and panel support sizes.

## Two other corrections/qualifications

**The k0=12 dielectric solve is not entirely all-near.** At 128 panels the exterior uses the all-near fallback, but the interior wavenumber is approximately 20.7865−0.2771i. Its near fraction is 71.09%, with 20 active translation groups. At k0=3 both regions are all-near. At 512 panels/k0=40 the exterior and interior near fractions are 27.70% and 11.26%, agreeing with Claude. The small k0=12 case therefore exercises part of the FMM, although it still has too much near coverage to establish large-scale convergence.

**Native batching already exists.** The prototype calls the existing batched near assembler, whose box arithmetic and thin-gap arithmetic have native implementations; the native near route is available on this host. Some geometry bookkeeping, scheduling and special-function evaluation remain outside those C routines. More batching/fusion or a different construction layout may help, but “put it in native code” is not a complete diagnosis of the setup cost. Profile the remaining work before choosing that optimization.

Claude's preconditioner warning is sound. The successful 512-panel factors occupy about 8 MiB, versus 16 MiB for that entire dense system matrix, and still require roughly 150 iterations per angle. The earlier 152/148 iteration results reproduce in Claude's runs. They are not evidence that similarly favorable RAM or iteration counts survive full-scale dielectric/coated geometries. Product and preconditioner partitions can be designed separately; shrinking one need not mechanically shrink the other, but the total memory/time tradeoff must be measured.

## Savings we can support

| Item | Supported result | Practical limit |
|---|---|---|
| Reusable Galerkin products | About 30×/23× S/W in the new 4k control; the previous 16k result was about 43×/24× and Claude reproduced its cached times | Component operations, not complete-solve speedups |
| Streamed point-near construction | Prior matched experiment: 0.904 → 0.374 GiB, 58.6% lower peak | Construction memory for that point-kernel case; not a 59% whole-solver RAM reduction |
| 16k reusable versus native-wrapper peak | Prior 2.10 GiB versus 1.24 GiB; Claude reproduced roughly 2.12 GiB | This version uses MORE peak RAM than that native wrapper, despite much faster repeated products |
| Near-block ILU | Prior/Claude: hard TE/TM converged in 152/148 iterations; simple controls exhausted 480 | Needs large-scale convergence and factor-storage testing |
| Adaptive wideband or FMM/H-matrix hybrid | Targets the demonstrated quadratic near-field growth under fixed-frequency refinement | No defensible overall percentage saving yet; neither has been implemented/benchmarked here |

A 32 GiB desktop could benefit substantially if the dominant near storage is removed and a compact effective preconditioner is retained. The current evidence does not establish a universal model size, peak-RAM reduction, or end-to-end speedup for full-scale layered geometry. The inherited 27.6 GiB near-construction example is a count-based warning about this prototype, not a prediction for a future adaptive engine.

## Further investigation and scope

**Yes, further investigation is needed and justified.** In order:

1. Qualify a consistent near-quadrature and far-translation accuracy policy on thin gaps, corners, loss and tree transitions.
2. Compare a bounded adaptive-wideband prototype with Claude's FMM/local-H-matrix proposal on the same fixed-frequency refinement series and a thin coated geometry. Keep exact singular/very-near terms and audit the panel-pair partition.
3. Design and measure preconditioning with those operators, including scalable scaling, inverse/adjoint actions and condition/residual verification. Do not extrapolate the small ILU result.
4. Measure full setup + solve cost and peak RAM for 1/16/181 angles, then consider production routing and Windows packaging.

The recent experiments have focused on FMM because it offers substantial matrix-free potential. The broader investigation is **not FMM-only**. Direct Compressed improvements, selective inverse precision, disk-backed residual storage, directional H²/nested compression, formulation/preconditioner improvements and mesh/order adaptation remain candidates. See [METHOD_CHOICES.md](METHOD_CHOICES.md) for measured versus speculative benefits and why the hybrid is plausible but not a drop-in reuse of the current inverse.

Keep Dense and Compressed in production. One Automatic user workflow can eventually select the appropriate internal engine; the evidence still does not support a single numerical method as the best choice for every size, material and angle count.
