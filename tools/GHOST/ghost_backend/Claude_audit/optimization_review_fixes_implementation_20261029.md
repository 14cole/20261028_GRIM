# Implementation handoff: optimization review fixes

This implements the recommendations from Codex's review of `review_of_codex_optimization_followup.md`. The earlier local worker-memory optimization and material-junction fallback remain in place. This round is local and has not been committed or pushed.

## Correctness fix

`execution/memory_budget.py::MemoryBudget.require_reload` now performs one detailed worker-memory retry whenever a reservation refusal used a conservative worker RSS charge. The old extra condition comparing worker RSS against private commit and modeled overhead could skip that retry when parent RSS growth dominated the reservation calculation. The new tests reproduce both missed cases and confirm that a genuinely insufficient reservation still refuses. Successful admissions keep the cheap path. The retry refreshes live OS limits and records one admission decision.

`tests/test_incremental_worker_memory.py` covers worker-private suppression, modeled-overhead suppression, genuine refusal, and the single-retry behavior. Synthetic memory figures exercise the accounting without allocating gigabytes.

## Reporting and source encoding

The memory report explains that the last 16 worker samples may mix detailed and cheap readings. A cheap sample's zero unique-residency field means it was not measured for credit; calibration must use complete samples marked eligible for credit. This adds text only, with no extra OS queries or persistent sample history.

Nine maintained Python files were converted to ASCII escape spelling, with equal parsed syntax trees verified before writing. Runtime Unicode strings and material-header aliases are preserved. `tools/FREDDY/ibc/material_columns.py` received the identical edit to the GHOST parser; their byte-for-byte contract is intact. See `encoding_changes.json`, `companion_encoding.json`, and original-byte snapshots under `Codex_audit/optimization_review_fixes_20261029/`.

`tests/test_source_is_ascii.py` still checks maintained production, launcher and test sources. It excludes top-level audit/trial/scratch evidence archives, preserving historical measured snapshots. A scope regression ensures similarly named directories nested inside production remain covered. This is paired with the actual production-source repairs above.

## Validation

- Focused preflight: 94 tests and 83 subtests passed.
- One uninterrupted full suite: **2,787 tests and 1,065 subtests passed**, one expected Windows skip, in 1,250.13 seconds. The skipped directory-fsync test is POSIX-only.
- Full log and structured results: `Codex_audit/optimization_review_fixes_20261029/full_suite.log` and `full_suite_results.json`.

## Fresh timing confirmation

The four-run current/baseline/baseline/current comparison completed after the full suite, with no concurrent solver/test workloads launched by this task. The case was the 12 ft by 3 ft conducting inlet at 15 GHz, 361 angles, automatic CPU settings and a 12 GiB cap. The isolated baseline restored the seven original pre-construction files and omitted `compressed/construction.py`. Worker source hashes confirm the intended imports.

| Version | Run times (s) | Mean (s) |
|---|---|---:|
| Pre-check baseline | 115.572, 115.360 | 115.466 |
| Current | 115.377, 115.564 | 115.470 |

The net difference is **+0.004 s (+0.0035%)**, effectively tied. This supports the earlier under-1% expectation on this case, but two samples per arm are not a universal performance bound. Factorization alone was **+1.612 s** (17.656 versus 16.045 s), offset elsewhere in the solve. Stage timers overlap, so do not sum them or describe every stage as cost-free. Peak process-tree private memory ranged from 2.686 to 2.762 GiB across all four runs; no RAM reduction is established.

All runs certified at 14,295 nodes; VV and HH arrays are bit-for-bit identical across all four. No harness guard fired. Current runs each have **9 canonical construction records, 16,122 checks, 1,163 live checks and 14,959 bounded reuses**. The harness uses the canonical execution-system list rather than recursively double-counting channel/shadow copies.

`Codex_audit/optimization_review_fixes_20261029/verify_final.py` passed, checking frozen production hashes, baseline source hashes, suite exit status, both field arrays, construction counts and companion-parser identity. Evidence: `verification.json`, `confirmation/summary.json`, and raw `confirmation/runs/` artifacts. Production files were not changed during the full suite or A/B.

Recommended review focus: the removed worker-RSS comparison in the refusal retry, the new parent-RSS regression cases, and the maintained-source/evidence boundary in the ASCII test. The implementation corrects the edge case missed in the earlier conclusion that the retry covered all conservative-worker refusals.

## Scope and follow-up

Compressed remains the default. Dense and surface impedance remain explicit overrides. Forecast discounts remain disabled. This work adds neither a new backend picker nor saved solve-history learning.

The coated inlet's conditioning/rank behavior and the magnetic case's discretization/forecast scaling remain separate numerical studies. This implementation does not qualify those geometries or establish that every 12-foot material geometry fits 32 GiB.
