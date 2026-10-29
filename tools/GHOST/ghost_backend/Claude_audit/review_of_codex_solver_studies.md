# Review of Codex's 2D solver studies (commit 30ce6fb, 2026-10-29)

Reviewed:
- `Codex_audit/solver_studies_20261029/README.md`
- `Claude_audit/CODEX_SOLVER_STUDIES_REVIEW.md`
- The raw `request`, `result`, `metadata` and `monitor` files for all 45 runs
- The source behind the RAM explanation (`linalg/hierarchical.py::ordered_copy`, `linalg/residual_spool.py::copy_fits`, `twod/assembly/session.py::plan_paired_assembly`)
- The Automatic ranking code (`execution/policy.py::rank_candidates`)

This commit changes no production code. I read files only and reran nothing.

## Verdict

The study is accurate. Every number I checked matches the raw files:
- Each reported success has both a passed quality gate and mesh-convergence certification.
- All rejected and stopped cases are still visible.
- The timing comparisons are matched as claimed (same budget, four threads, alternating order).

I also accept the main correction to my last review. The material-filled inlet at 15 GHz **does fit**: it certified at 9.96 GiB with no spatial refinement. My concern that its mesh would triple did not happen.

One finding goes beyond Codex's report, and it is the most useful thing for you. The per-step timings show that **Automatic's time model is badly miscalibrated**. A hard-coded rule that puts dense first is what rescues the metal cases. Details are below.

## Numbers checked

| Claim | Raw files | OK? |
| --- | --- | --- |
| Dielectric inlet 3 / 10 / 15 GHz: 4.00 s / 57.95 s / 151.10 s; 0.542 / 4.585 / 9.960 GiB | Matches; all certified, final backend dense | Yes |
| Dielectric 15 GHz final mesh: 2,904 panels, 17,424 unknowns, no spatial refinement | Two steps, both at 2,904 panels | Yes |
| Dogleg metal 15 GHz: 42.59 s, 5.401 GiB | Matches | Yes |
| Coated inlet: 3 GHz condition 8.55e6, 10 GHz guard stop, 15 GHz rank > 214 | Matches; thicker coatings at 1.27e7 and 9.29e6 | Yes |
| Metal 15 GHz repeats: dense 86.40, Automatic 87.09, compressed 125.31 s | All 9 runs match; spreads under 0.2 s | Yes |
| Narrow 15 GHz repeats: 114.59 / 115.36 / 140.33 s | All 6 runs match | Yes |
| Hint pairs: 34.07 s vs 39.11 s median, 12.9% | Three pairs, 33.96–34.25 s vs 39.00–39.12 s | Yes |
| Budget probes: dense at 8 GiB 104.63 s / 3.99 GiB; Automatic at 6 GiB 98.30 s / 3.70 GiB | Matches | Yes |
| Cylinder checks: worst error 0.0123 dB, complex error 0.0888% | 0.01229 dB (dielectric), 0.000888 (PEC) | Yes |
| Lifecycle RSS span 2.156 MiB | 2,260,992 bytes | Yes |
| Prototype: all six variants fail | `passed: false`; worst solution difference 3.85 | Yes |
| High-contrast cases are admission refusals, not out-of-memory crashes | Peak RSS 0.12 / 0.29 GiB; refusal text shows the forecasts | Yes |

The RAM explanation checks out against the source. The ordered matrix copy and the paired TM matrix are both optional, and each is admitted separately against live headroom (`copy_fits`, `plan_paired_assembly`). That is why the 12 GiB dense run peaks at 9.66 GiB while its base forecast is 6.09 GiB. Codex is right that this doesn't make admission unsafe.

## New finding: Automatic's time model is wrong, and a hard-coded rule masks it

Every adaptive step records Automatic's predicted cost for dense and compressed. Those are relative work units, so only the ratio matters. Compare that ratio with the measured step times:

| Step (15 GHz) | Unknowns | Predicted dense ÷ compressed | Measured dense ÷ compressed | Faster in practice |
| --- | ---: | ---: | ---: | --- |
| Metal, 3rd step | 8,592 | 1.22 (compressed faster) | 19.4 / 28.7 s = 0.68 | Dense |
| Narrow, 3rd step | 9,792 | 1.28 (compressed faster) | 25.7 / 33.6 s = 0.76 | Dense |
| Metal, final | 14,295 | 1.95 (compressed 2x faster) | 57.0 / 68.1 s = 0.84 | Dense |
| Narrow, final | 15,849 | 1.96 (compressed 2x faster) | 77.0 / 75.7 s = 1.02 | Tie |
| Dielectric, final | 17,424 | 0.07 (dense 14x faster) | 109.1 / 91.7 s = 1.19 | Compressed (one run) |

On the metal steps, the model predicted compressed would be faster, yet Automatic picked dense. The reason is `execution/policy.py:117-120`: whenever compressed would use the H-matrix and dense fits, dense is moved to the front regardless of cost. The step metadata still says "Lowest predicted cost among compatible backends", which is not true when that rule fires.

So Automatic gets the metal cases right, but for the wrong reason. On the dielectric, the model was wrong the other way: it predicted compressed 14x slower, but compressed was faster. The likely cause is the same over-estimated rank that inflates the compressed RAM forecast, since the cost model uses those ranks.

What this costs you:
- **Small meshes (under about 14,000 unknowns):** dense is clearly faster. Automatic correctly picks it.
- **Around 15,000 to 17,000 unknowns:** the two take about the same time, or compressed is faster. Compressed uses about a third of the RAM there (2.6 vs 8.5 GiB narrow; 4.0 vs 10.0 GiB dielectric). Automatic picks dense and spends that RAM for no speed gain.
- **Mixing works.** The 6 GiB Automatic run used dense on the small meshes and compressed on the final one. Its final compressed step took 68.5 s, the same as an all-compressed run (68.2 s), so switching mid-run costs nothing. On the dielectric, a dense-then-compressed run would come to about 133 s, against 151 s all-dense, at well under half the RAM. That is untested: the forced-compressed final step may have reused a tighter inverse learned on its earlier compressed step.

**Recommendations:**
1. When the dense-first rule fires, say so in the selection reason. This is small and needs no new data.
2. Recalibrate the `stage_work_v6` cost model against these per-step timings. There are now about 30 certified runs with matched settings. This is also the most direct route to the time estimates you asked about earlier.
3. After that, consider letting compressed win near-ties above about 16,000 unknowns, where it costs no time and saves 4 to 6 GiB. Confirm with one repeated dielectric dense-then-compressed run first.

## Smaller observations

- **The RAM budget changes the speed, not just the RAM.** The final dense metal step took 56.9 s with a 12 GiB budget and 75.2 s with 8 GiB, because the larger budget admits the optional 3.0 GiB ordered copy. Any time estimate needs to take the budget into account. Codex flagged this; I'm adding the step-level number.
- **Coated inlets.** I agree this is the top capacity problem. Even at 3 GHz the coated inlet used 5.7 GiB before failing, against 0.54 GiB for the material-filled inlet. That suggests the thin shell, not the wavelength, drives the mesh size. Useful offline diagnostic: record the condition estimate and the field change under refinement with the gate disabled, without changing production. That would show whether the 1e6 gate is protecting accuracy here or is simply strict for thin coatings. Codex's point stands that production gates should not be loosened.
- **Prototype and chunking.** I agree with both conclusions. The simple block preconditioners failed (400 iterations, errors up to 6e-6). Chunked solving must keep the global coupling, so disk storage alone won't help with conditioning or rank limits.
- **Preview line.** You declined it, so I've dropped it. With the dielectric case fitting without refinement, there's also less reason for it.

## Answer to the original questions, updated with this data

- **Is dense worth keeping?** Yes. On metal at 15 GHz it is 18 to 31% faster (26 to 39 s), repeatably. That's under two minutes, as you said, but real.
- **Does 15 GHz fit in 32 GB?** Yes for the metal, dogleg and moderate-dielectric 12 x 3 ft inlets (2.3 to 10 GiB). No, for now, for the thin-coated inlet (conditioning and rank, not RAM) and the high-contrast material (the solver refuses it before starting because the forecast exceeds the RAM budget).
- **Biggest speed and RAM win still available:** fix Automatic's time model so it uses compressed on large meshes where it ties dense. That would save several GiB with no time penalty.
