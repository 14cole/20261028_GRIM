# Claude handoff: resource efficiency follow-up — 29 October 2026

Review [the implementation and study report](../Codex_audit/resource_efficiency_20261029/README.md) against base `50d2c64`. The user wants useful throughput and reliable capacity, with 90% RAM utilization only a soft goal. The current changes do not pursue a fixed occupancy percentage.

## Code change

`compressed/runtime.py` now includes excess live residency in fallback workspaces **before** sizing the automatic retained-payload allowance. The old ordering added residency afterward and could refuse a reduced-storage plan prematurely. The same extra residency is retained in `process_geometry_bytes`, so later incremental reload checks account for it.

The synthetic counterexample previously refused 6.251 GiB against 6 GiB. The new forecast admits 6.000 GiB by shrinking automatic payload from 3.108 to 2.108 GiB. This is an admission correction, not an assertion that every numerical inverse fits that smaller allowance. The actual operator, inverse and numerical certification still enforce their limits. Explicit payload settings are unchanged, excessive workspaces still fail, and speculative forecasts do not activate a plan.

Review the two-pass calculation, active fallback envelope and subsequent reload accounting. New regression coverage is in `tests/test_fallback_residency_sizing.py`; the exact source hashes and before/after reproduction are in the report folder.

## Study interpretation

The four/automatic/automatic/four inlet comparison measures existing production CPU profiles with identical monitoring and request settings. Automatic already selects eight assembly threads on this machine. Four-worker controls set both assembly and BLAS to four; automatic BLAS retains its existing behavior. The measured advantage is therefore a profile comparison, not a speedup caused by this patch or a worker-only experiment.

The completed four inlet runs took 149.88, 117.90, 117.50 and 149.73 seconds respectively. Automatic averaged about 21% faster, with certified fields agreeing to within 4.13e-16 relative error (roundoff; the four-worker controls match exactly). Keep the existing automatic defaults; no new backend picker, tuning mode, persistent preferences or OS configuration change is warranted by this comparison.

The report also covers the 12-foot by 3-foot dogleg contour at 15 GHz with PEC, moderate dielectric and high-contrast magnetic material. Refer to `summary.json` for the final status of each case and regression counts. Distinguish certified passes, admission refusals, numerical failures and external trial guard stops. A forecast refusal is not proof of actual peak memory demand, and a time guard stop is not a solver correctness failure.

## Priorities

- Check that live residency is counted once in each workspace/payload calculation and remains visible to reload admission.
- Preserve explicit caps, active-worker allowances and numerical acceptance checks.
- Judge benefits by elapsed time and completed useful work; unused RAM is not itself an optimization defect.
- Do not describe the current study as proof that arbitrary high-contrast or intricate geometries fit on a 32 GB PC.

Final validation: **624 tests and 114 subtests passed** across 45 affected files. Six real solves certified. The moderate dielectric dogleg completed in 370.85 s with 6.017 GiB peak tree RSS; the magnetic stress case was rejected in geometry preparation by the 100,000-panel request limit, not a RAM check. All 85 historical evidence hashes remain unchanged.
