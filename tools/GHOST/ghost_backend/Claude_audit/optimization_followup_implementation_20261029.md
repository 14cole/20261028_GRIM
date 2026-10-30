# Optimization follow-up for Claude review

The preceding completed implementation was pushed to `origin/main` as `6c73ccd`. The follow-up below is local and has not been pushed.

## Implemented

1. **Cheaper live worker charges.** Profiling found 3.49 seconds in detailed worker-memory queries. `compressed/worker_pool.py` now offers a fresh RSS/private-commit probe for incremental allocation checks. `execution/memory_budget.py` charges it conservatively and grants no worker residency credit from it. Whole-footprint admission retains detailed unique-residency sampling. Platforms without private commit in the cheap probe retain full sampling.
2. **Exact recheck before an RSS-bound refusal.** If shared pages in the conservative worker charge would reject a reservation, refresh once using unique residency and live limits. Accept only if that refined check fits; otherwise reject. This preserves the user's concern about false low-memory refusals while keeping fitting allocations fast. Large-allocation checks, pending holds, peers and explicit/scheduler limits remain enforced.
3. **Decline incompatible junction projection.** Combined D/W junction endpoint routing does not commute with the P2-to-P3 map, while S/K' keep independent endpoints. `twod/assembly/polynomial_pair.py` now declines these layouts through the existing independent-assembly fallback. The optional mode remains off by default. No physical equations, default solver choice or numerical tolerances changed.

The changed tests are `test_incremental_worker_memory.py`, `test_polynomial_pair.py`, and `test_junction_pair_fallback.py`. The final run passed **184 tests and 27 subtests**. Both dense and compressed optional-junction solves match independently assembled fields exactly. The previously observed projection mismatch is now explained and blocked from optional reuse; it was not hidden by loosening an error threshold.

## Measurements

- Two runs per arm: **120.308 -> 117.108 seconds**, saving **3.199 seconds / 2.66%** relative to the pushed version. Worker-query cost fell **3.489 -> 0.219 seconds**. All four inlet runs certified and produced bit-for-bit identical fields. No total RAM saving was demonstrated.
- The paired trial predates the final exact-on-refusal refinement. A final-code inlet confirmation took **117.243 seconds** with identical fields. The old and final file hashes are preserved separately as `timing_source_hashes.json` and `source_hashes.json`.
- The 12 ft by 3 ft moderate-dielectric dogleg at 15 GHz certified in **366.133 seconds**, with **6.830 GiB** sampled peak private memory under a 12 GiB cap. Its fields exactly match the prior reference.
- The coated 15 GHz inlet did not finish within the 240-second trial guard; peak private memory was about 4.20 GiB. The magnetic dogleg was rejected by refinement forecasts and the panel limit. The 2 GiB conducting-inlet stress trial did not certify before its 180-second guard. None is a successful capacity qualification, and forecast numbers are not measured minimum RAM requirements.
- Three two-request concurrency trials reduced combined mean wall time **15.810 -> 11.971 seconds**, about **24.3%**, with both cases certified and serial/parallel field differences at most 4.28e-15. Overlap disabled observation reuse, reservations remained distinct, and cleanup completed. Cases were a 3 GHz conducting inlet and 1 GHz moderate-dielectric dogleg, 13 angles each, with 4 GiB caps.

The concurrency harness initially hit an intermittent Windows folder-creation permission error, which caused a barrier timeout before one solver started. The error was captured on repetition; precreating output folders fixed the harness. Three subsequent runs passed. Raw failures and the stricter-than-planned initial bitwise-concurrency verification assertion remain saved; the final verifier uses the study's original 1e-10 comparison threshold, not a changed solver tolerance.

## Review focus and remaining work

Please review the separation between worker charges and residency credit, the one-time exact refusal recheck, and the junction routing/interpolation incompatibility. The working tree contains earlier local raw evidence intentionally excluded from the preceding push; avoid treating all untracked archives as new production changes.

Detailed evidence and the reproducible scripts are in `Codex_audit/optimization_followup_20261029/`. Read `README.md`, `summary.json`, `junction_reason.json`, and the final test logs. The full suite was not rerun this turn; the existing ASCII-source issue remains.

Further optimization should focus on coated/magnetic numerical scaling and qualification rather than shaving the remaining approximately 0.2-second worker-query cost. Compressed stays default, dense/impedance stay manual overrides, and forecast discounts stay disabled. These trials do not prove arbitrary 12-foot complex materials fit or certify within 32 GiB, and chunking alone does not solve discretization or convergence limitations.
