# Impedance alternative: measured findings

**Recommendation: retain an explicit, experimental surface-impedance override for suitable strongly absorbing materials. The speed and memory savings justify using the existing IBC capability. Keep full material as the default physics model.**

This experiment uses the current compressed solver default on both sides of the comparison. The benefit comes from changing the material approximation, not choosing a different factorization backend. Production source and defaults were not changed. A ready-to-use experimental geometry snapshot is included; the existing opaque TYPE 2 / IBC path already supports it.

## Matched numerical comparisons

All timings include both polarizations, 361 requested directions and production mesh certification. Error statistics use 360 unique angles. The 15 GHz scaled models have lengths 2.88, 7.2 and 14.4 inches respectively; they are not full-size 15 GHz bulk references.

| Case | Bulk time | Impedance time | Speedup | Time saved | Peak private GiB, bulk / impedance |
|---|---:|---:|---:|---:|---:|
| 1/50 size, 15 GHz | 25.48 s | 0.95 s | 26.8x | 24.53 s | 1.217 / 0.435 |
| 1/20 size, 15 GHz | 79.94 s | 1.56 s | 51.2x | 78.38 s | 2.390 / 0.537 |
| 1/10 size, 15 GHz | 104.60 s | 3.28 s | 31.8x | 101.32 s | 3.951 / 0.707 |
| Full 12 ft x 3 ft, 1.5 GHz | 86.17 s | 3.27 s | 26.3x | 82.90 s | 3.926 / 0.699 |

Windows private bytes are committed private memory, not physical RAM; measured tree RSS is in the complete run table below. Timings are single measurements for matched pairs, so decimal precision is retained for reproducibility, not a statistical confidence claim. These measured matched-case savings do not establish a five-minute saving; the full-size 15 GHz benefit is demonstrated feasibility where the bulk request fails its panel limit.

| Case | Polarization | Relative complex-field L2 error | Maximum field error / peak | RCS error p95 / max, dB | Angles included in dB check |
|---|---|---:|---:|---:|---:|
| 1/50 size, 15 GHz | VV | 0.416% | 0.230% | 0.149 / 0.291 | 322/360 |
| 1/50 size, 15 GHz | HH | 1.224% | 0.730% | 0.537 / 0.663 | 344/360 |
| 1/20 size, 15 GHz | VV | 0.267% | 0.101% | 0.031 / 0.059 | 196/360 |
| 1/20 size, 15 GHz | HH | 0.753% | 0.257% | 0.387 / 0.490 | 228/360 |
| 1/10 size, 15 GHz | VV | 0.191% | 0.050% | 0.018 / 0.036 | 99/360 |
| 1/10 size, 15 GHz | HH | 0.586% | 0.150% | 0.280 / 0.369 | 113/360 |
| Full 12 ft x 3 ft, 1.5 GHz | VV | 0.191% | 0.050% | 0.018 / 0.036 | 99/360 |
| Full 12 ft x 3 ft, 1.5 GHz | HH | 0.586% | 0.150% | 0.280 / 0.369 | 113/360 |

All matched cases use one contour at different electrical sizes, not independent shape families. For these constant material properties, the full-size 1.5 GHz case and 1/10-size 15 GHz case are electrically equivalent; their agreement is an implementation/scaling check, not independent physics qualification. The complex-field errors include phase and every angle. The dB statistics include only bulk RCS within 30 dB of its peak, because division by a deep null exaggerates tiny absolute differences. This is not a claim of the same dB accuracy at every angle. In the 1/10-scale case, unfiltered maximum dB differences reach 3.23 dB for VV and 2.00 dB for HH. Complete unfiltered maxima, phase differences and worst-angle locations are retained in summary.json.

## Full size at 15 GHz

The 12 ft x 3 ft impedance model passed certification in **67.82 seconds**, using peak tree RSS **1.94 GiB** and private memory **2.73 GiB**. A fresh repeat took **67.73 seconds**. It published 10,143 scalar mesh nodes on 3,381 panels at polynomial degree 3.

The matching full-material request failed during geometry preparation after 5.51 seconds: `Discretization exceeds the configured panel limit.`. Its peak private memory was only 0.60 GiB. This is a mesh-cap failure, not evidence of RAM exhaustion. Earlier helper-based counting found approximately 320,091 reference panels before grading/certification against the configured 100,000-panel cap.

**There is no full-size bulk reference at 15 GHz, so no measured bulk-versus-impedance error bound can be claimed there.** The completed 1.5 GHz full-size comparison, 15 GHz scaled concave comparisons and 15 GHz analytic cylinders support the approach, but do not prove accuracy for all full-size 15 GHz cavity responses or corners. One-degree sampling does not bound unsampled angular features.

## Numerical checks and failures

The full-size 2 GHz bulk case was refused after its adaptive attempt reached a linear fallback forecast of 33.57 GiB for 85,462 DOFs, beyond the 12 GiB trial reservation. The run ended after 56.65 seconds. This is a forecast refusal, not an observed allocation of 33.57 GiB or proof that every possible discretization requires that amount. The paired impedance request passed in 3.68 seconds. Therefore no 2 GHz full-size model-error statistic is reported.

Increasing requested panel density preserved the matched-model conclusions. Actual adaptive panel counts and degrees are retained; the controller can change basis and refinement strategy, so higher requested density does not always double final nodes.

| Check | VV maximum change / peak | HH maximum change / peak |
|---|---:|---:|
| s50_impedance | 0.009400% | 0.006176% |
| s20_bulk | 0.000040% | 0.000227% |
| s20_impedance | 0.004221% | 0.003450% |
| s50_bulk_dense_refinement | 0.000046% | 0.000006% |
| full_impedance_repeat | 0.000000% | 0.000000% |
| full_impedance_refinement | 0.000942% | 0.000245% |

The 1/50-scale bulk refinement failed in compressed GMRES at its convergence cap. A deliberately selected dense reference at the same higher requested density passed, and agreed with the original compressed bulk result to less than 0.000046% of peak field. That dense run is an accuracy cross-check, not part of the primary compressed-versus-compressed timing comparison. The failed run is retained; no convergence criterion was weakened. This is a concrete follow-up case for the compressed solver, independent of whether impedance is adopted.

## Independent physics comparison

The cylinder series comparison covered both polarizations, radii from 5 to 457.2 mm, and frequencies 2, 3 and 15 GHz. At 15 GHz the largest absolute RCS difference was **0.005685 dB**. Across the same radius grid at 2 and 3 GHz the maxima were 0.487257 and 0.148899 dB. Scaled Bessel functions avoid overflow, adding 20 exterior modes confirms truncation stability, and six finite cases agree with the repository reference formulas within 1e-10 relative error.

The negative control matters: for a moderate, weakly lossy dielectric (relative permittivity 4 - 0.04j, permeability 1), some 15 GHz cylinder errors exceeded **12 dB**. The surface approximation must not be applied automatically to arbitrary dielectrics, thin layers, transmitting structures, or materials whose penetration and internal resonances matter.

## Optional override and upkeep

Use the existing opaque surface model with **Zs = 77.95162063057441 - 27.198691307695334j ohms** for this specific representative material. The source material is eps_r = 101.19 - 11.88j, mu_r = 3.45 - 3.47j, assumed constant in this experiment. `experimental_full_size_impedance_geometry.json` is the explicit converted snapshot; each run/request.json also includes runnable solver arguments. The original full-material snapshot remains intact.

This needs no extra factorization mode. If exposed more prominently in the UI, it should be a per-material, explicitly selected “Surface impedance approximation” with the chosen impedance, frequency dependence and model identity recorded in the results. Full material should remain available for reference and for materials that do not meet the approximation assumptions. Do not silently select it because a bulk request is large or fails.

The next useful qualification work is representative measured material data, additional inlet widths and corner radii, sharper angle sampling around critical lobes/nulls, and an independent full-size high-frequency reference where feasible. These would expand the qualified use cases; they are not reasons to discard the already useful explicit experimental input.

## Complete trial record

| Run | Status | Solve or failure elapsed, s | Peak RSS GiB | Peak private GiB |
|---|---|---:|---:|---:|
| s50_bulk | passed | 25.479 | 0.616 | 1.217 |
| s50_impedance | passed | 0.950 | 0.162 | 0.435 |
| s20_bulk | passed | 79.945 | 1.528 | 2.390 |
| s20_impedance | passed | 1.560 | 0.141 | 0.537 |
| full_impedance | passed | 67.816 | 1.936 | 2.730 |
| s50_impedance_refined | passed | 0.639 | 0.086 | 0.348 |
| s50_bulk_refined | failed | 146.947 | 2.142 | 3.009 |
| s20_impedance_refined | passed | 1.367 | 0.114 | 0.432 |
| s20_bulk_refined | passed | 135.775 | 2.874 | 3.740 |
| s10_bulk | passed | 104.604 | 3.074 | 3.951 |
| s10_impedance | passed | 3.284 | 0.152 | 0.707 |
| s50_bulk_dense_refined | passed | 23.390 | 3.101 | 3.668 |
| full_bulk | failed | 5.512 | 0.393 | 0.598 |
| full_impedance_repeat | passed | 67.725 | 1.949 | 2.759 |
| full_impedance_refined | passed | 67.734 | 2.197 | 3.102 |
| full2_bulk | refused | 56.645 | 2.647 | 3.418 |
| full2_impedance | passed | 3.679 | 0.222 | 0.741 |
| full15low_bulk | passed | 86.167 | 3.060 | 3.926 |
| full15low_impedance | passed | 3.271 | 0.162 | 0.699 |

16 certified successes and 3 retained failures. These are solver experiments and analytic assertions, not a rerun of the full regression suite; production source was unchanged.

![Geometry, timing and angular patterns](comparison.png)

See [METHOD.md](METHOD.md) for exact metrics, monitoring limits, assumptions, primary-source context and reproduction. Machine-readable evidence: [summary.json](summary.json), [analytic.json](analytic.json), [environment.json](environment.json), plans and individual runs. The companion Claude handoff highlights the approximation boundary and compressed-refinement failure.
