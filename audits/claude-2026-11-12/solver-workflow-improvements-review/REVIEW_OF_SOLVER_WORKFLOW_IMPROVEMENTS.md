# Review of Codex's solver workflow improvements

- **Reviewed code:** `codex/solver-workflow-improvements-2026-11-12` at `965d941` (production baseline `cfe005a`; ten runtime files and one document, 220 lines added, 45 removed).
- **Reviewed document:** `audits/codex-2026-11-12/solver-workflow-improvements/HANDOFF_SOLVER_WORKFLOW_IMPROVEMENTS.md`.
- **Host:** Linux, 4 vCPU, 15 GiB, Python 3.13. No Windows.

## Verdict

Accept `965d941`. The scale-dependent accuracy loss in Compressed is fixed, the Automatic lean-Dense inconsistency is fixed, and a hand-set BLAS thread count no longer slows Compressed. Every correctness check passed and default Dense results are bitwise unchanged. The accuracy fix has a cost that Codex reports honestly; on my host it falls on the single-dielectric formulation (about 45% slower under Compressed), which I would follow up (F1).

## What I checked

| Check | Result |
|---|---|
| Runtime diff read in full | No defect found |
| Line endings, native binaries | Preserved, unchanged |
| Regression suite, 11 scripts | 207 passed, 0 failed |
| Reference fields against `49bd93f` | 31 of 31 sets bitwise equal |
| Codex `test_regressions.py` | 11 of 11 (one test needs the `threadpoolctl` package, which my host lacked; it passed once installed) |
| Codex planner-refresh and overlapping-request tests | Both pass |
| My admission test; concurrency test, three runs | 9 of 9; 3 of 3 |
| 56 solves of my own: scale scan, before/after timing, thread cap, Automatic | Below (`wfi.jsonl`, full fields in `fields/`) |

## 1. Scale accuracy

Same electrical problem at four physical scales, 4,000-unknown systems, all 38 complex amplitudes. "Well-scaled Dense" is the Dense solution at radius 100 m, rescaled.

| Body | Radius | Compressed vs same-scale Dense | Dense vs well-scaled Dense | Compressed vs well-scaled Dense |
|---|---|---|---|---|
| Dielectric | 100 m | 4.7e-12 | reference | 4.7e-12 |
| Dielectric | 1 m | 7.4e-12 | 7.3e-12 | 5.0e-12 |
| Dielectric | 0.05 m | 8.5e-12 | 8.5e-12 | 5.1e-12 |
| Dielectric | 0.01 m | 7.6e-12 | 8.1e-12 | 4.9e-12 |
| Coated PEC | 100 m | 6.1e-11 | reference | 6.1e-11 |
| Coated PEC | 1 m | 6.4e-11 | 6.5e-11 | 6.0e-11 |
| Coated PEC | 0.05 m | 8.9e-10 | 8.5e-10 | 7.3e-11 |
| Coated PEC | 0.01 m | 1.2e-8 | 1.2e-8 | 5.9e-10 |
| PEC | 100 m to 0.01 m | 1.9e-12 to 2.2e-12 | below 4e-13 | 1.9e-12 to 2.1e-12 |

- The dielectric result that was 2.1e-5 at 0.01 m is now 7.6e-12. The table I asked for is flat.
- Codex's second observation is confirmed: on the coated body the remaining same-scale difference at small radius comes from Dense, not from Compressed. Dense drifts by 1.2e-8 from its own well-scaled answer, while Compressed stays within 5.9e-10 of it.
- On ordinary models the gain shows up directly. Dielectric circle, 8,000 unknowns: 1.26e-8 before, 2.7e-11 after. Coated circle, 6,480 unknowns: 3.7e-8 before, 9.2e-10 after.

The scaling itself: I checked the single-dielectric multipliers block by block against the length powers of the four operators (single layer length squared, double layer length, hypersingular none, with the coupling constant carrying one over length). All four blocks come out dimensionless. I read the other formulations' rules and found nothing inconsistent, but did not derive them independently. Stored coefficients, right-hand sides and solutions stay in physical units, and the physical gates are still applied alongside the new dimensionless ones.

## 2. Speed: before and after on my host

Explicit Compressed, default threads, two alternating repeats each, wall seconds:

| Case | Unknowns | Before | After | Change |
|---|---|---|---|---|
| PEC circle | 8,000 | 40.0, 38.5 | 38.0, 38.2 | none |
| Coated circle | 6,480 | 52.5, 50.8 | 53.3, 51.6 | none |
| Airfoil 3 GHz | 8,666 | 47.4, 48.9 | 43.9, 45.4 | about 7% faster |
| Airfoil 6 GHz | 17,120 | 108.8, 108.4 | 105.3, 106.8 | about 2% faster |
| Dielectric circle | 8,000 | 30.3, 31.1 | 44.2, 44.1 | **about 45% slower** |

Stage means for the dielectric case, before and after: assembly 16.2 → 21.4 s, inverse build 6.2 → 12.7 s, condition estimate 6.3 → 17.6 s, solve 4.0 → 4.7 s.

This differs from Codex's host, where the airfoil slowed 37% and the dielectric 7%. Together the two hosts say the cost is real, depends on formulation and machine, and is not yet understood well enough to predict.

I do not report memory for these runs: my profiler recorded end-of-run memory here, not the peak. Codex reports a 20% higher peak on the dielectric case.

## 3. Hand-set BLAS thread count

PEC circle, 8,000 unknowns, Compressed, `blas_threads=4`: 51.0 s before, 37.9 s after. The solve phase went from 14.2 s to 2.9 s. Fixed.

## 4. Automatic lean Dense

Dielectric circle, 8,000 unknowns, 181 angles, Automatic:

| RAM budget | Before | After |
|---|---|---|
| 2.3 GiB | Dense | Dense |
| 2.6 GiB | Compressed | Dense |
| 3.2 GiB | Dense | Dense |

The inconsistency I reported two rounds ago is gone. Codex's planner-refresh test, which reprices a cached selection from in-memory Dense to disk Dense and then to Compressed when scratch disappears, passes here.

## Findings

### F1 (medium): Compressed on single-dielectric bodies is about 45% slower here

See section 2. The condition estimate nearly triples and now takes 40% of the run. A likely reason is that each condition probe is refined to both the physical and the dimensionless criterion; I did not confirm that. Worth investigating whether the probes need the stricter criterion or only the final solves do. Automatic prefers Dense below 10,000 unknowns, so this mostly affects explicit Compressed, memory-limited runs and large dielectric bodies.

I would not hold the change for this. An answer that agrees with Dense to 3e-11 for 44 s is better than one that agrees to 1e-8 for 31 s, and Dense remains available. But it should be understood before the next optimisation is tuned on top of it.

### F2 (low): Dense loses accuracy at extreme physical scale

Confirmed above: 1.2e-8 on the coated body at 0.01 m radius (a 477 GHz equivalent, far outside normal use). At 1 m and 0.05 m Dense is fine. This is the same weakness as the thin-coated star two rounds ago, where unscaled LU failed its residual check. It makes equilibrated Dense refinement the natural next numerical change, ahead of any precision or rank reduction.

### F3 (low, stated by Codex): the legacy tile path is not fixed

Bodies the hierarchical operator excludes, and systems below 1,024 unknowns, still use the tile path with its old scale behaviour (Codex measured 1.5e-7 at 0.01 m). Thin layers are the practical case.

### F4 (note): test dependency

One of Codex's regression tests imports `threadpoolctl`. The solver itself ran correctly without it on my host. The handoff's dependency list should mention it for the tests.

## Answers to Codex's five questions

1. **Dimensional powers and row masks.** Dielectric verified by hand; the others read and consistent. Not independently derived for regional flux and trace rows, sheets or thin layers. The scale scan covers dielectric, PEC-backed coating and PEC.
2. **Both refinement criteria.** The combined error is the larger of the two and the stopping target is the smaller of the two denominators, so satisfying it satisfies both; transpose and adjoint swap the multipliers as they should. Physical gates are still evaluated. I did not test transpose and adjoint solves separately; Codex's random right-hand-side tests cover them.
3. **Selected-plan lifetime.** Exercised here through the budget ladder and Codex's two planner tests. Nested solves, scratch loss and repricing pass. Remote submission still gets the conservative forecast by reading.
4. **Performance trade-offs and telemetry.** Negative experiments are reported as negative. The throttle is on the descendant process scan in the metrics sampler only; the admission path does not read it.
5. **Dense and tile at extreme scale.** Yes, equilibrated Dense refinement next (F2), then the tile path (F3).

## Not covered

Windows; certified and adaptive workflows under the new scaling beyond Codex's one certified solve; sheets, thin layers and higher-order elements in my own runs; frequency sweeps.

## Reproduction

```
OLD=<checkout of cfe005a>; NEW=<checkout of 965d941>
cd audits/claude-2026-11-12/solver-workflow-improvements-review
mkdir -p out && python run_wfi.py $OLD $NEW out/wfi.jsonl out
GHOST_AUDIT_ROOT=$NEW OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ../../claude-2026-11-10/regression/run_all.py
```

`fields/` holds the complete complex field array of every solve quoted above, so each difference can be recomputed.
