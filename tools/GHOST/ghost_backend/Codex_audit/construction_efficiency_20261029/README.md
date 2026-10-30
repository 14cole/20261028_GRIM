# Construction-check efficiency follow-up

This implements the recommendations from `Codex_audit/claude_inverse_trial_review_20261029/README.md`. The prior inlet trial showed 12.25 seconds of added solve time (12.1%) with unchanged fields, and exposed duplicated diagnostic counts in its summary.

## Implementation

### Reuse bounded headroom observations

Every construction allocation group still checks its allowance and takes an atomic pending hold. For small steps in a single request, a recent live observation can supply that allowance without querying the operating system again. The reuse conditions are deliberately bounded:

- The next allocation is less than 16 MiB.
- The observation is less than 50 milliseconds old.
- Cumulative modeled allocations, including the first checked group, stay within the lesser of 64 MiB and 1% of the request reservation.
- Each allocation consumes the observed remaining headroom; finishing or freeing a temporary does not refund that allowance.
- Current numeric ownership cannot grow beyond what the observation and intervening allocations explain.
- No overlapping request, nested pending construction group, or changed explicit/scheduler cap is present.
- Any registered workers are idle, have a complete live memory sample, and retain the same generation, payload, worker count, closure state and process IDs. Unknown or active worker owners prevent reuse.

New ownership registrations, memory-plan changes and other live memory checks invalidate the observation. Exhausted headroom, quota or time triggers a fresh check, which can refuse before allocation. Large allocations always get a fresh check. Overlapping requests, active workers, changed worker identities and incomplete worker samples keep fresh checks throughout. This is an internal observation policy, not a new user control or a forecast discount.

The already-required live check now supplies the process sample used for construction diagnostics. It also reuses the process and stable-reservation readings from the same `limit()` call instead of immediately querying them again. Build entry/exit samples remain. External memory changes can occur between observations; the bounded observation lifetime and allocation quota limit this exposure, but do not constitute a guarantee against arbitrary external memory pressure.

### Explicit, consumable reload coverage

Allocation groups now default to **zero** included reload allowance. A caller may explicitly designate part of its modeled allocation for reloads. Payload plus workspace consumes this allowance under the shared lock, so it cannot cover the same bytes repeatedly. Any unpriced or excess reload must pass its own live check. No production construction caller currently opts into an exemption.

### Preserve useful diagnostics

Successful construction checks are summarized through live/reused/admitted/refused counters instead of filling the 64-event memory report. Refused checks still retain their full event. The report distinguishes summarized checks from older detailed events discarded by the ring limit. Phase and reload events therefore remain visible longer.

Shadow metadata now compares the **accounted construction allowance** with the construction forecast and flags when the former exceeds the latter. It explicitly labels this as an accounted/model comparison, not a measured peak, and does not change admission. Checkpoint process samples retain their separate meaning and limitations.

## Validation and timing artifacts

`validate.py` runs regressions with bounded failure reports and workspace-local temporary directories. The initial restricted full-suite attempt encountered Windows hard-link permissions. The unrestricted run then exposed a packaging fixture that recursively copied its own nested temporary directory. After fixing that fixture, the campaign resumed the remaining and failed test files. Raw logs and timestamped result records preserve all attempts.

`confirmation/ab.py` repeats the ordinary inlet trial in current/baseline/baseline/current order. It uses the same 12-foot by 3-foot conducting inlet, 15 GHz, 361 angles, automatic CPU profile and 12 GiB cap as Claude's trial. It ran serially after tests. The baseline restores the seven saved pre-construction source files in an isolated copy. Only validated trial-local temporary directories are removed afterward; production source and previous results are preserved.

The new summary counts construction evidence exclusively from `experimental_cpu.systems[*].preconditioners[*]`. It does not recursively sum duplicated channel summaries and shadow records. Workers record source hashes, and raw field arrays are retained for direct comparison. `confirmation/implementation_hashes.json` freezes all four changed production files, including the worker identity method. `verify_final.py` checks those hashes, fields, normal exits and test coverage without running another solve.

### Final inlet comparison

| Metric | Pre-construction baseline | Optimized safeguards |
|---|---:|---:|
| First solve | 116.251 s | 120.070 s |
| Second solve | 115.810 s | 119.477 s |
| Mean solve | 116.030 s | 119.773 s |
| Mean factorization | 16.236 s | 20.189 s |
| Sampled peak tree private memory | 2.703-2.748 GiB | 2.696-2.748 GiB |

The safeguards now add **3.743 seconds (3.226%)**. Claude's earlier paired comparison found **12.251 seconds (12.107%)**. This is a substantial reduction in measured overhead, but **does not meet the proposed 2% threshold**. Host throughput differed between the historical and final comparisons, so the absolute solve durations should not be treated as a direct before/after speedup. There are only two repetitions per arm and one geometry.

All four final runs passed quality and mesh-convergence certification, reached 14,295 nodes, exited normally, and triggered no monitor guard. VV and HH fields are **bit-for-bit identical** across all four runs. There is no demonstrated whole-solve RAM saving; the optimization removes repeated memory-query work while preserving allocation accounting.

Each optimized solve records 9 builds and 16,122 construction admissions. Only 1,164-1,165 require live observations; 14,957-14,958 consume a bounded recent observation (about 92.8%). The request ledger records 16,500 total checks, 16,122 summarized construction checks, 64 retained detailed events and 314 older omitted events. None of the final retained events is a successful construction admission, so construction checks no longer crowd out phase/reload diagnostics. No construction refusal occurred in this trial; refusal behavior is covered by focused tests.

The earlier pilot in `runs/` and `ab_console.log` used a stricter no-worker reuse rule. Its first current run took 124.809 seconds versus 116.654 and 116.116 seconds for the baselines. Inspection showed repeated queries for idle workers; the pilot was stopped during its fourth arm, and its partial results were preserved. The final idle-worker identity refinement was validated separately and measured in the complete `confirmation/` trial. Do not combine the two experiments or count the incomplete pilot as a fourth result.

### Regression results and unresolved findings

The broad campaign observed all **2,767 originally collected test IDs** across `full_suite_part1_results.json` and `full_suite_part2_results.json`. This is coverage of the collected suite, **not a claim that all cases passed**. It predates the final idle-worker refinement; that refinement and its affected paths subsequently passed **134 focused tests**. The final fixture recheck passed **170 tests and 101 subtests**. Counts overlap and must not be added together.

Stale fixtures were updated to match existing behavior: compressed as the default, explicit dense selection when mocking the dense path, explicit adaptive selection when testing the compatibility picker, and forwarding the existing surface-wave argument through test wrappers. The package-layout fixture now excludes audit/trial/scratch directories from a package copy and recognizes two already-tracked root files. These changes do not remove numerical assertions or alter production solver selection.

Two existing failures remain:

1. `test_polynomial_pair.py::PolynomialPairTests::test_projected_matrix_matches_independent_galerkin_assembly`: the optional junction projection differs from independent assembly by 0.0365775 (TE) and 0.0558107 (TM), versus a 2e-10 tolerance. The pre-task and current modules produce identical matrix hashes and errors. Other tested geometries pass. `projection_before.json`, `projection_current.json` and `projection_probe.py` preserve the evidence. The optional sharing path remains off by default; it needs a separate numerical investigation before expansion.
2. `test_source_is_ascii.py`: existing Unicode in source and historical audit snapshots violates the repository's ASCII check. An attempted encoding-only cleanup was reverted byte-for-byte because the material parser must also retain byte identity with the companion project. `ascii_preservation.json` records the reversion; the companion material contract passes in the final recheck. This broader cleanup remains unresolved.

`validation_summary.json` records coverage and unresolved failures. `trial_comparison.json` records verified trial metrics, and `source_hashes.json` identifies the final implementation and changed tests. The final affected-path tests are clean; the full suite is not.

## Remaining qualification

Keep the bounded observation policy and explicit reload accounting. Do not expand the reuse window or enable forecast discounts on the strength of this single case. The remaining 3.23% overhead merits profiling live worker-memory queries if further optimization is pursued; this experiment does not isolate their exact share of the remaining cost. Separate tight-memory, competing-request, coated and bulk-material trials are still needed before claiming broad large-geometry capacity. Resolve the optional junction-projection discrepancy before considering wider use of that separate optimization.

## Decisions preserved

Compressed remains the default; dense and surface impedance remain explicit overrides. Storage forecasts, mesh certification, numerical tolerances and the existing RAM budget policy are unchanged. Shadow observations remain confined to the current single-frequency request, with no persistent solve history. This work does not establish capacity for arbitrary coatings, bulk magnetic material, or more complex inlet geometries. No push is included in this task.
