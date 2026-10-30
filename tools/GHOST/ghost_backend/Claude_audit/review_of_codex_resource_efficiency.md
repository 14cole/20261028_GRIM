# Review of Codex's resource-efficiency handoff (commit 743d639, 2026-10-29)

Reviewed:
- `Claude_audit/codex_resource_efficiency_implementation_20261029.md` (the handoff)
- `Codex_audit/claude_calibration_review_20261029/`: Codex's review of my last report
- `Codex_audit/resource_efficiency_20261029/`:
  - README, `summary.json`, `plan.json` and `host_context.json`
  - the before/after fallback reproduction
  - the seven run folders
- The diff of `743d639` in `compressed/runtime.py` and the new `tests/test_fallback_residency_sizing.py`

GitHub `main` is at `743d639`. I read code and saved results only; I ran no tests or solves.

**Context:** you've clarified that 90% RAM use is a soft goal, not a requirement. I've reviewed against that: reliable solves, accurate estimates and speed come first.

## Verdict

**The code change is correct.** When a hierarchical solve falls back to tile assembly, unexplained live memory (for example native caches) is now counted *before* the automatic storage allowance is chosen, not after. A run that used to be refused (6.25 GiB needed against 6.00 GiB allowed) is now admitted with a smaller storage allowance. That extra memory is also carried into later reload checks.

**The study is useful, and its biggest result isn't the code change.**
- The default automatic CPU profile (8 assembly threads) solves the inlet **21% faster** than the 4-thread setup that every audit trial so far has used (117.7 vs 149.8 s).
- The dogleg runs certify: metal in 66 s, moderate dielectric in 371 s.
- The high-contrast magnetic dogleg hits the 100,000-panel limit before any RAM is used. **That case probably doesn't need more RAM.** It looks like a good fit for the impedance-boundary formulation GHOST already has (see Finding 2).

Codex's corrections to my last report are mostly right, and I accept them.

## Codex's corrections to my last report

| My claim | Correction | Position |
|---|---|---|
| The slowdown is definitely the PC, and the code is cleared | The A/B clears the code only for the tested inlet. The morning run (124 s) and the afternoon A/B (157 s) used **different measurement harnesses** (`trace_solve.py` vs `study.py` with a background process sampler), so the cause of the 26% shift isn't isolated. | **Accept.** I missed that the harness changed. |
| Future timing comparisons are unreliable until the slowdown is explained | Too sweeping. Same-session, same-harness A/B tests stay valid. | **Accept.** |
| A 4–6 GiB pagefile minimum would let solves reach 90% "without paging" | Untested. The arithmetic says about 1.75 GiB more commit would make physical RAM the binding limit, but "no paging" isn't something the solver can guarantee, since Windows can still trim working sets. | **Accept.** Given your soft-goal clarification, I **withdraw the pagefile recommendation**. Revisit only if a real solve is refused on commit. |
| "Only another program can trigger pagefile growth" | Not shown. The 10-second hold only shows that growth didn't happen in that trial. | **Accept.** |
| Tile meshes are never the memory-binding ones | Not true for unsupported configurations, thin magnetic layers, or a large hierarchical solve that falls back to tile | **Accept.** The worker-allowance conclusion (leave it alone) still holds. |
| My worker table's "peak private" column | It summed each worker's lifetime peak. The simultaneous maximum is slightly lower: 0.35 / 0.65 / 1.28 GiB for 2 / 4 / 8 workers. | **Accept.** It doesn't change the conclusion. |

## Code change checked

| Check | Finding | OK? |
|---|---|---|
| Live memory counted once | `price()` adds `extra = live − process_geometry` to the geometry term, the peak, and every phase and non-storage term. It does this on both passes of the two-pass sizing, so the allowance is chosen with the extra memory already included. The admission limit credits the same `live` as resident, so it's compared like with like. | Yes |
| Visible to reload checks | The recorded fallback envelope takes the larger `process_geometry_bytes`, which now includes `extra`. The test confirms that a 3 GiB reload is then refused. | Yes |
| Explicit storage unchanged | With an explicit 4 GiB cap, the allowance stays at 4 GiB and the run is refused if it doesn't fit. Live memory of 7 GiB against a 6 GiB cap gives storage 0, and the run is refused. | Yes |
| Speculative forecasts | Don't replace the active plan (tested) | Yes |
| Tests | 624 tests and 114 subtests across 45 files; three new | Yes |

**One minor note.** `live` is the whole process RSS. If the other polarization's tile operator is already resident at fallback time, its bytes appear in both `live` and the plan's storage term. That over-counts, which is safe, and the old ordering did the same. It would only matter for a fallback on the second polarization of a run that's already near its cap. Worth one regression later, not a fix now.

## Finding 1: keep the automatic CPU profile, and stop comparing against 4/4

| Inlet at 15 GHz | 4 assembly / 4 BLAS | Automatic (8 assembly, adaptive BLAS) |
|---|---:|---:|
| Repeat 1 | 149.88 s | 117.90 s |
| Repeat 2 | 149.73 s | 117.50 s |
| Peak RAM | 1.84–1.88 GiB | 1.87–1.88 GiB |
| Peak commit | 2.25–2.27 GiB | 2.67–2.69 GiB |

The repeats are tight (within 0.4 s), and the alternating order rules out drift. Automatic costs about 0.4 GiB more commit and no extra RAM. Since that's the default in the GUI and drivers, real runs were already getting the faster profile. Every earlier audit time quoted at "4 threads" understates real-world speed by about 20%.

**Suggestion:** use the automatic profile for future audit trials, so that measured times match what you'll actually see.

## Finding 2: the magnetic stress case is a formulation choice, not a RAM limit

The magnetic dogleg is a solid 12 ft × 3 ft block of material with ε = 101.19 − 11.88j and μ = 3.45 − 3.47j. At 15 GHz:

| Quantity | Value |
|---|---:|
| Refractive index n = √(εμ) | about 20.1 − 9.8j |
| Wavelength inside the material | about 1.0 mm |
| Distance over which the field falls by a factor of e | about **0.33 mm** |
| Thinnest part of the body | 6 in (152 mm), about 460 decay lengths |
| Surface impedance Z/Z₀ = √(μ/ε) | about 0.207 − 0.072j |

Resolving a 1 mm interior wavelength along about 9 m of contour needs well over 100,000 panels, so the panel limit is the right answer for a full-material solve. But nothing reaches the interior: the field dies out within a millimetre. This is the textbook case for a surface-impedance (Leontovich) boundary, which applies when |n| ≫ 1 and the body is many decay lengths thick. GHOST already has a Robin/impedance formulation (`twod/formulations/robin.py`) that supports closed impedance contours, and the geometry format has an `ibcs` entry.

With an impedance boundary of about 0.207 − 0.072j on the same contour, the mesh would be sized by the free-space wavelength, like the metal dogleg: about 10,500 nodes and about 1 minute, not over 100,000 panels.

**How to validate it before relying on it:**
1. Run the full material model and the impedance model on the same dogleg at a frequency where the material mesh fits, for example 2–3 GHz. There the decay length is about 2 mm and the panel count is roughly 5–7 times smaller.
2. Compare the RCS. Expect the largest differences near the concave corners, where the impedance approximation is weakest.
3. If they agree within your tolerance, use the impedance model at 15 GHz.

This is a modelling choice that changes the physics approximation, so it's yours to make. I'd do it before spending any effort on fitting the full-material version.

## Finding 3: the dielectric dogleg is the realistic capacity case

The moderate-dielectric dogleg certified in 370.85 s at a 6.0 GiB peak (6.9 GiB commit). Its two certification solves took 150 s (P2) and 221 s (P3). That's about 20% of a 32 GB machine, so it has room to spare. It has no independent reference, only the production quality and mesh-convergence gates, as Codex notes.

If faster dielectric runs matter, the cost is in material operator assembly and the P3 step, not memory. That's where a future speed study should look.

## Recommended order

1. Keep `743d639`. No changes needed.
2. **Your call:** try an impedance boundary for the high-contrast magnetic case. Validate it against the full material model at 2–3 GHz first (about 4 solves).
3. Use the automatic CPU profile in future audit trials.
4. No pagefile, worker-allowance or utilization-percentage work, given your soft-goal clarification.
