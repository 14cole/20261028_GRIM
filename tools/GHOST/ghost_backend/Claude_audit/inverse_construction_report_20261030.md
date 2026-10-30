# Inverse-construction checks: audit report (2026-10-30)

**Status:** the code audit is complete, but **the timed inlet run has not happened yet.** The Remote Control request to run it on your PC was declined, so nothing was started. The A/B script is ready (see "Timed inlet run" below). Until it runs, every end-to-end timing figure in this report is an estimate.

Full code review: [review_of_codex_inverse_construction.md](review_of_codex_inverse_construction.md)

## Summary

Codex's change is **correct and safe to keep**.
- The inverse being built is now counted against the request's memory while construction runs.
- Each expensive step checks live RAM and commit headroom before it allocates.
- Two requests can't both claim the same headroom.
- The old inverse stays counted while its 1e-10 replacement is built.
- The numerics are unchanged: both Codex benchmarks give bit-for-bit identical solutions.

This meets the safety prerequisite I set last round before any forecast correction. Codex has added that correction in **shadow mode only**: it's recorded in metadata and never used for admission.

The cost is time. Each check takes about **0.47 ms**, so small inverse builds run 2.6–3.3× slower.

## Measured so far (Codex's microbenchmark: 2 workers, 1 BLAS thread)

| Unknowns | Checks per build | Build before | Build after | Peak private memory |
|---:|---:|---:|---:|---|
| 1,536 | 398 | 0.080 s | 0.262 s | 244.6 → 245.3 MiB (unchanged) |
| 4,096 | 814 | 0.241 s | 0.632 s | 516.2 → 516.5 MiB (unchanged) |

## Estimate for the ordinary inlet (to be confirmed by the timed run)

On the automatic profile, the inlet took 117.9 s in total, of which factorization was 16.4 s (resource-efficiency study, `inlet_auto_1`).

The check count grew from 398 to 814 checks per build as the size went from 1,536 to 4,096 unknowns. At that rate, an inverse of about 14,000 unknowns would need about 2,000 checks, or roughly 1 s. The certification builds several inverses (each mesh, each polarization, plus the 1e-10 upgrades), so I expect **about 4–8 s added, or 3–7% of the total.**

That's an extrapolation, and it could be higher on tile meshes. There, 8 live assembly workers get a memory snapshot on every check, whereas the benchmark had only 2.

## Findings and suggested fixes

| # | Finding | Fix | Priority |
|---|---|---|---|
| 1 | About 0.47 ms per check, most of it OS memory queries and worker snapshots | Keep the arithmetic retained-cap checks on every step. Only do the live OS check when a step adds more than about 16–32 MiB, or when unchecked growth since the last live check passes about 64 MiB or 1% of the reservation. Drop the second process sample per step. | Medium |
| 2 | Construction checks fill the 64-entry memory report and push out the phase and reload checks that explain a refusal | Don't log admitted construction checks there, since they're already summarised in the construction evidence. Keep logging refusals. | Low |
| 3 | A reload skips its check whenever it's smaller than the current step, even though that step's model never priced a reload | Make the step's allowance explicit and use it up with each reload | Low (latent) |
| 4 | Shadow observations are only recorded in single-frequency requests | Run the qualification cases one frequency at a time | Note |
| 5 | The shadow record compares retained storage but not the construction peak | Add the ratio of measured to forecast build peak, with an under-prediction flag | Low |
| 6 | 260 tests were run, against 624 in the last full suite | Run the full suite before pushing | Low |

Accepted from Codex: my "stop escalating after a memory refusal" idea saves little. The later refusals are priced before assembly and cost under 2.2 s in total.

For the 2 GHz case, the shadow mode can't qualify it directly: its cubic mesh is refused before it ever runs. Qualification needs cases where both meshes fit.

## Timed inlet run (ready, not yet run)

Script: `Claude_audit\inverse_checks_ab\ab.py`
- It builds a baseline copy of `ghost_backend` with Codex's seven saved baseline files restored and `construction.py` removed. Everything else is identical.
- It then runs the ordinary 15 GHz inlet four times: current, baseline, baseline, current. It uses the automatic CPU profile, a 12 GiB cap and the same environment as Codex's resource-efficiency study.
- It records total and stage times, check counts, peak memory, and field differences between the arms. Results go to `summary.json`.
- Expected run time is about 9 minutes. It deletes its temporary copy afterwards.

To run it yourself, from that folder: `python ab.py` (with the Python that GHOST uses). Leave the PC otherwise idle while it runs.

**How to read the result:**
- **Under about 2% slower:** keep the checks as they are, and fix 1 is optional.
- **About 2% or more:** do fix 1 before pushing.
- **The fields must be identical between arms.** Any difference is a bug.

## Recommended order

1. Run the timed inlet A/B, either yourself or by allowing the session on your PC.
2. Make fixes 2 and 3, plus fix 1 if the A/B shows 2% or more. Then run the full test suite, and push if you're happy (your call).
3. Shadow qualification on single-frequency material cases where both meshes fit.
4. Enable the forecast correction only if no case under-predicts. Then retry the 2 GHz full-material run.
