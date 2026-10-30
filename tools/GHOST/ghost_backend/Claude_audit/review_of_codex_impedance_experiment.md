# Review of Codex's impedance experiment, and improvements found (2026-10-29)

Reviewed:
- `Claude_audit/impedance_alternative_experiment_20261029.md` (the handoff)
- `Codex_audit/impedance_alternative_20261029/`: README, METHOD, `summary.json`, `analytic.json`, the experimental geometry, and all 19 run folders. I read the forecast plans, factor metadata and failure logs.
- `Codex_audit/claude_efficiency_review_20261029/`: Codex's review of my last report
- Source, for the improvement analysis:
  - `compressed/memory.py` (`hmatrix_storage`)
  - `compressed/factor.py` (GMRES and preconditioner escalation)
  - `twod/adaptivity.py` (adaptive-to-reference fallback)

GitHub `main` is still `743d639`. This round changed no production code; the experiment lives only on your PC. I read code and saved results only; I ran no tests or solves.

**Your direction:** the surface (impedance) solver is an override only. Codex's recommendation already matches that, and everything below assumes it.

## Verdict on the experiment

**The experiment is sound, and it supports an explicit override.**

| Result | My check |
|---|---|
| Full 12 ft × 3 ft dogleg at 1.5 GHz: bulk 86.2 s vs impedance 3.3 s; complex-field error 0.19% (VV) / 0.59% (HH); RCS within 0.04 / 0.37 dB above −30 dB | Matches `summary.json` and the run results |
| Full size at 15 GHz: impedance certifies in 67.8 s, and 67.7 s on repeat with identical fields; bulk stops at the panel limit | Matches |
| Impedance value 77.95 − 27.20j Ω | 376.73 × √(μ/ε) = 376.73 × (0.2069 − 0.0722j). Correct. |
| Analytic cylinders: 0.0057 dB worst case at 15 GHz; the moderate dielectric fails by over 12 dB | Matches. That failure is exactly why it must never be applied automatically. |

The error measures are well chosen: complex fields with phase across all angles, and dB only above −30 dB with the angle counts shown. Codex is careful to say that the 1/10-scale 15 GHz case and the full-size 1.5 GHz case are the same electrical problem, and that nothing qualifies full-size 15 GHz against bulk.

## Codex's corrections to my last report: accepted

| My claim | Correction | Position |
|---|---|---|
| "Use an impedance boundary of about 0.207 − 0.072j" | That's Z/Z₀. GHOST's IBC entries are in **ohms**, 77.95 − 27.20j Ω. The contour must also become TYPE 2 (opaque IBC), not TYPE 3 with an IBC flag. | **Accept.** Entering my number would have been wrong by a factor of 377. |
| A 2–3 GHz match would qualify 15 GHz | Sharp corners, grazing incidence and cavity effects change with frequency | **Accept.** |
| About 10,500 nodes and about 1 minute | Not established at the time | Accept as unestablished then. The run has since confirmed it: 10,143 nodes and 67.8 s. |
| "Probably doesn't need more RAM" | Bulk peak memory is still unknown | **Accept.** It describes the alternative model, not the bulk requirement. |
| Every earlier audit time understates real speed by 20% | Shown only for the inlet on this host | **Accept.** |
| Possible double count of the other polarization at tile fallback | Not shown to be the same allocation | **Accept.** I withdraw it until someone has a counterexample. |

## Improvements found

### 1. The hierarchical memory forecast over-estimates lossy high-contrast materials by 2–7×, and that probably caused the 2 GHz refusal

Forecast against measured, from the saved plans and factor metadata of the four bulk runs that completed:

| Bulk run | Forecast path | Operator forecast → measured | Inverse forecast → measured | Inverse rank forecast → measured max |
|---|---|---:|---:|---:|
| 1/50 size, 15 GHz | sampled tiles | 0.33 → 0.33 GiB (**1.0×**) | 0.19 → 0.05 GiB (3.7×) | – / 93 |
| 1/20 size, 15 GHz | hierarchical model | 0.91 → 0.38 GiB (2.4×) | 0.73 → 0.16 GiB (4.7×) | 864 / 105 |
| 1/10 size, 15 GHz | hierarchical model | 3.10 → 0.84 GiB (3.7×) | 2.60 → 0.35 GiB (7.5×) | 1,658 / 115 |
| Full size, 1.5 GHz | hierarchical model | 3.10 → 0.84 GiB (3.7×) | 2.60 → 0.37 GiB (7.0×) | 1,658 / 124 |

The over-forecast grows with electrical size. The cause is in `compressed/memory.py:hmatrix_storage`: it takes the **largest |k| of any medium**, here the magnetic interior at about 22× free space, and applies it to every block. It also ignores loss, as its own note says ("Magnitude-only rank estimate; material loss does not reduce the admission allowance"). Two effects are therefore missed:
- Exterior blocks oscillate at the free-space k₀, not at 22 k₀.
- Interior interactions fall off as exp(−Im k · r). At 2 GHz, Im k is about 409 rad/m, so blocks more than about 7 cm apart are below 1e-12, while the body is 3.7 m long.

The measured ranks show this: the operator's maximum rank is 38 and the inverse's 124, against a forecast of 1,658.

**Consequence:** the full-size 2 GHz bulk run was refused at a 33.57 GiB forecast (operator 13.7 GiB plus inverse 11.1 GiB) against 12 GiB. At the over-forecast measured just 0.5 GHz lower (3.7× and 7×), the real need is likely well under 12 GiB. That's an estimate, not a measurement, but it fits the "false refusal" pattern you wanted removed.

**Suggested fix, without a blind discount** (Codex rightly refused to discount loss on one experiment):
- When the geometry-only hierarchical model is what *refuses* a run, first **sample a handful of real blocks** (cross-approximation on a few near and far tiles, which takes seconds) and reprice from the measured ranks, as the tile path already does. The tile path's sampled forecast was exact here (1.0×).
- Refuse only if the sampled forecast still doesn't fit.
- Keep every live memory check.

This needs no new physics and no user option, and it applies to every lossy material, not just this one. Calibrate first against the four runs above plus the earlier moderate-dielectric inlets, where the over-forecast was 1.4–3.1×.

### 2. A refused fallback hides why the adaptive mesh was rejected

The 2 GHz bulk run went through three stages:
1. the adaptive candidate (coarsening 8), rejected
2. the conservative retry (coarsening 4), rejected
3. the linear reference mesh (85,462 unknowns), refused at 33.57 GiB

The final error mentions only the memory refusal. The reason for the rejections in steps 1 and 2 (`reason` in `twod/adaptivity.py:_run_certified`) is stored only in metadata of a *successful* fallback, so it is lost when the fallback itself is refused. You can't tell whether a convergence gate or something else forced the 7× larger linear mesh.

**Fix:** append the adaptive rejection reason to the fallback's memory error. Also save the adaptive steps in the failure record. This is a small diagnostic change.

### 3. Compressed numerical failures should say whether dense would fit

The 1/50-scale refined bulk run failed in compressed GMRES after 147 s, even after the built-in preconditioner upgrade (`compressed/factor.py:_refine`, where 1e-10 is the last escalation). The same mesh with dense certifies in **23.4 s**, matching the lower-density compressed result to 0.000046%.

Under your decision (compressed by default, dense only as an override), automatic retry with dense is correctly not done. But the error currently gives no hint that dense is the remedy.

**Fix:** on a compressed numerical rejection, add the dense memory estimate for the same mesh to the message, and say whether it fits the current reservation. For example: "Dense override would need about X GiB (fits / does not fit)." This keeps dense as an override and costs no extra solve.

Separately, this run is a good small reproducer for compressed robustness on high-contrast media. About 25 s per attempt makes it cheap to iterate on.

### 4. The surface-impedance override should guard its own use

Since it stays an explicit override, make it hard to misuse:
- **Enter ε and μ, and let the code compute Zs in ohms** at each frequency. This removes the factor-of-377 trap I fell into, and handles dispersive data when it exists.
- **Show an applicability check when the override is chosen**, not an automatic switch:
  - |n| ≫ 1 (here about 22)
  - the thinnest body section compared with the decay length (here 152 mm vs 0.33 mm)
  - a warning near sharp corners or for low-loss materials (the moderate-dielectric control erred by over 12 dB)
- **Label outputs** as "surface impedance approximation of material X", with Zs recorded, as Codex proposes.
- **Never offer it as a reaction to a refusal**, as Codex already says.

## Recommended order

1. **Improvement 1** (sample before refusing on the hierarchical path). It's the only one that turns likely false refusals into solves. Calibrate against the four saved bulk runs; then the full-size 2 GHz bulk run is the natural test (one solve, with your go-ahead).
2. Improvements 2 and 3: small diagnostic changes that make failures actionable.
3. Improvement 4, if you want the impedance override in the GUI rather than as a hand-edited geometry file.
4. Keep the experimental impedance geometry as Codex supplied it. No production default changes.
