# Review of Codex's Automatic selection changes (commit 5460aa2, 2026-10-29)

Reviewed:
- `Codex_audit/response_to_claude_solver_studies_review.md`
- `Codex_audit/automatic_selection_20261029/` (README, the 13 runs, calibration)
- The production diff `30ce6fb..5460aa2` in `execution/policy.py`, `execution/selection.py`, `execution/timing_history.py` and `twod/adaptivity.py`

I read the code and the raw run files. I reran nothing.

## Verdict

The code is correct and safe, and every number I checked matches the raw files. Codex's corrections to my last review are fair, and I accept them below.

The main limit: the new rule that lets timing evidence override the dense preference will almost never fire in normal use. Automatic's choices on large refined meshes are therefore unchanged. The matched runs show that dense on the smaller meshes followed by compressed on the final mesh can beat both pure modes. Whether Automatic should do that is a policy decision for you, and the current data is mixed, as shown below.

## Numbers checked

| Claim | Raw files | OK? |
| --- | --- | --- |
| Dielectric 15 GHz: dense 181.05 s, compressed 161.06 s, mixed 145.08 s | Two runs each, spread under 0.2 s | Yes |
| Dielectric peak RSS: 5.82–5.85 / 3.99 / 4.68 GiB | Matches | Yes |
| Narrow inlet 15 GHz: dense 115.49 s, compressed 137.71 s, mixed 112.97 s | Two runs each | Yes |
| Narrow inlet peak RSS: 8.49–8.55 / 2.58 / 4.68–4.73 GiB | Matches | Yes |
| All 12 matched runs certified | Quality gate and mesh convergence both pass | Yes |
| Coated-inlet diagnostic: 42.35 s, 5.56 GiB; condition 2.8e6–1.4e7; residual 1.31e-9 | Matches | Yes |

## Where Codex corrected me, and I agree

- **Mixed dielectric time.** My 133 s was two step times added together. The measured mixed run takes 145 s, still 20% faster than dense, but my "no time penalty" went beyond the evidence.
- **Dielectric cost ratio.** The 0.073 ratio I quoted covered both initial meshes together. Per mesh it is 0.058 and 0.083, still badly wrong.
- **Recalibration alone cannot change Automatic's choice.** Codex showed the dense-first rule overrides even 100 s vs 1 s timings. I missed that.
- **16,000-unknown threshold.** Not supported by three fixtures.
- **Thin-shell cause.** Unproven; I withdraw it.

## Code review

| Change | Assessment |
| --- | --- |
| Ranking diagnostics (`policy.py`) | Correct. Records the cost winner, the selected backend, the admitted set, the exclusions, and whether the dense preference changed the result. `ranking_reason` now describes what actually happened, which fixes the misleading "lowest predicted cost" text. |
| Selection metadata (`selection.py`, `adaptivity.py`) | Correct. Reused forecasts and retained request preferences are labelled separately from the underlying decision, and `cost_scope` marks costs as covering several meshes. |
| Timing override (`timing_history.py`) | Correct and conservative. The dense preference is dropped only for qualified nearby or stage evidence: 3 to 5 paired samples per backend, bounded spread and a clear winner. Exact-match medians alone don't qualify. |
| Tests | 162 unique tests pass. The new `test_selection_explanations.py` covers the cases Codex lists (too few or noisy samples, changed reservations, batch limits). |

**How often the override can actually fire:**
1. **Requests:** the timing evidence is applied once per request (`options.py:610`). The override needs a paired history of both backends, 3 to 5 runs each, in the same nearby family. A normal user running Automatic only ever builds dense history, so it will rarely qualify.
2. **Later adaptive meshes:** the larger, spatially refined meshes call `select_backend` directly (`adaptivity.py:195`). That path uses the default dense preference and never sees timing evidence. The request-level choice is carried over only to the first two meshes (`len(steps) < 2`). But the final mesh is where the narrow inlet's crossover happens.

So Automatic still picks dense for the large final meshes. Codex's README says as much ("does not promise the mixed-run timing for a new cold request"). It's worth stating plainly because it determines whether the measured gains reach you: right now they don't.

**Minor:** the coated diagnostic's `metadata.json` records `quality_gate.passed: true` and `mesh_convergence_certified: true`, because the gate was relaxed in that process. Only `result.json` (`status: diagnostic`) and `original_quality_gates.json` mark it as uncertified. The audit runner should also mark relaxed-gate runs as uncertified in `metadata.json`, so its fields can't later be mistaken for certified results.

## What the matched runs say about mixing backends

Final-mesh step time, dense vs compressed, from all matched runs so far:

| Fixture | Final unknowns | Dense final step | Compressed final step | Mixed vs all-dense: time | Mixed vs all-dense: peak RAM |
| --- | ---: | ---: | ---: | --- | --- |
| Ordinary metal inlet | 14,295 | 57.0 s | 68.1 s | about 11 s slower if mixed (not run) | about 9.7 → 3.7 GiB (6 GiB Automatic run) |
| Narrow metal inlet | 15,849 | 78.0 s | 74.9 s | 2.2% faster (measured) | 8.5 → 4.7 GiB |
| Material-filled inlet | 17,424 | 139.0 s | 102.8 s | 19.9% faster (measured) | 5.8 → 4.7 GiB |

All three fixtures follow one trend: the bigger the final mesh, the better compressed does on it. Even where mixing costs time (the ordinary inlet), it roughly halves peak RAM. That makes this a speed-versus-RAM tradeoff, not a free win.

Codex is right that three fixtures can't fix a threshold. The cheapest test of whether the trend holds is two held-out fixtures with final meshes around 13,000 to 20,000 unknowns: one metal and one material-filled, with dense and mixed runs, two repeats each. That is about 8 solves, roughly 20 minutes.

## Calibration and coating

- **Calibration.** I agree a single global time scale shouldn't ship: the held-out dielectric error was 36.7x. That error comes mostly from the compressed cost on material bodies, which uses the over-forecast inverse rank (squared). A model fitted separately for metal and material bodies would be the next thing to try offline. It doesn't need to block anything.
- **Coated inlet.** This is the strongest new result. All eight gate checks failed only on conditioning, while the fields barely changed under refinement (3.9e-5 relative, 0.005 dB). The gate is stopping results that look stable.
  - **A candidate criterion to test offline:** gate on the condition number times the measured backward error, which bounds the solve's own error, instead of the condition number alone. Here that is about 1.4e7 x 1e-12 ≈ 1e-5 relative error.
  - **The caveat:** a condition gate may also be guarding against physical near-resonance, which a solve-error bound doesn't catch. So it has to be checked against an independent coated reference before anything changes, as Codex says. Production gates stay as they are.

## Decision options: what Automatic should do on large refined meshes

> **Superseded (2026-10-29):** Cole chose to make compressed the default, with dense as an explicit override. See `review_of_codex_compressed_default.md`. These options are kept for the record.

This is a policy choice for Cole, with Codex reviewing. In all three options, memory admission, the numerical gates and dense itself stay unchanged.

| Option | What happens | For | Against |
| --- | --- | --- | --- |
| **A. Run the held-out test first** (recommended) | About 8 solves (roughly 20 minutes): two new 15 GHz fixtures with final meshes around 13,000 to 20,000 unknowns, one metal and one material-filled, comparing all-dense with dense-then-compressed, two repeats each. Same budget, threads and gates as the matched study. No policy change until the results are in. | Tests whether the size trend holds on shapes it wasn't derived from. Cheap. | Delays any RAM or speed gain, and adds 8 solves on your PC. |
| **B. Keep dense-first** | No change. Automatic keeps picking dense for every mesh dense fits, unless qualified paired timing history exists (rare). | Behaves the same on every machine, and is fastest on the ordinary metal inlet (about 11 s). | Leaves 20% speed (material-filled inlet) and about 4 to 6 GiB of RAM on the table for large final meshes. |
| **C. Prefer lower RAM on near-ties now** | On spatially refined meshes, choose compressed when both backends are admitted and the predicted times are close. That needs a working definition of "close", which the current cost model can't yet provide reliably. | Roughly halves peak RAM on large meshes, and is faster on the material-filled and narrow inlets. | About 11 s (19%) slower on the ordinary inlet. Rests on three fixtures, and the cost model's tie-breaking is unreliable until recalibrated. |

If option A shows that compressed matches or beats dense on the final mesh above some size for both new fixtures, the follow-up would be a narrowly scoped version of C:
- It would apply only to spatially refined meshes, with both backends admitted.
- It would be recorded in the selection reason.
- It would be regression-tested on the existing matched fixtures.

If A doesn't confirm the trend, B stands.

## Recommended next steps

1. Mark relaxed-gate diagnostic runs as uncertified in `metadata.json`. Trivial.
2. **Your decision:** keep dense-first on large refined meshes (today's behaviour), or test letting compressed take the final mesh when both fit. If you want the test, run the ~8-solve held-out check above before any policy change.
3. Independent coated-inlet reference, comparing the condition-only gate against the solve-error-bound gate.
4. A cost model fitted separately for metal and material bodies, evaluated offline only.
