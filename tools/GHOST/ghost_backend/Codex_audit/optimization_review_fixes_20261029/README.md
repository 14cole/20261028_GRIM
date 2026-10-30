# Optimization review fixes

Implements the actionable findings in `Codex_audit/claude_optimization_review_20261029/README.md`. This work is local; no commit or push is included.

## Changes

- Reservation-bound refusals that used cheap worker RSS now always receive one detailed retry. The retry refreshes OS headroom and unique worker residency. It no longer incorrectly tests worker RSS against modeled overhead/private commit while ignoring the parent-RSS branch of the charge. Successful allocations retain the cheap path, and a genuine refusal still rejects after the detailed check.
- Regressions cover both missed branches (worker-private and modeled-overhead suppression), a genuine-capacity refusal, exactly one retry and one recorded admission decision.
- The memory report explains that cheap samples' zero unique-residency field is unmeasured, not zero consumption. Calibration requires a complete full sample. No new sample cache, OS queries or persistent history were added.
- Nine maintained Python files now spell Unicode characters with ASCII escapes. Their parsed syntax trees are unchanged, preserving runtime strings and Greek/ohm material-header support. The FREDDY copy of the material parser received the identical edit, maintaining the byte-for-byte shared-parser contract.
- The source-encoding check covers production, launchers and tests. Top-level audit/trial/scratch directories are explicitly treated as evidence archives, consistent with the package-copy boundary, so historical snapshots retain the exact bytes used for previous measurements. A regression checks that similarly named nested production directories remain covered. Production Unicode was repaired rather than hidden by this exclusion.

`encoding_changes.json` and `companion_encoding.json` record original/final hashes and AST equality. `before/` retains original bytes as text snapshots. `ascii_cleanup.py` records the conversion and checks the companion file has not changed before editing it.

## Validation and artifacts

The focused preflight passed **94 tests and 83 subtests**, including the new memory cases, source encoding, material interoperability and run controls. One uninterrupted full-suite invocation then passed **2,787 tests and 1,065 subtests**, with one expected Windows skip, in **1,250.13 seconds**. The skipped directory-fsync test is POSIX-only. Exit code was zero. `full_suite.log` and `full_suite_results.json` preserve the raw output and structured outcomes; subtests are separate outcome rows, not additional collected tests.

After the full suite, `confirmation/ab.py` ran current/baseline/baseline/current serially on the same 12 ft by 3 ft conducting inlet at 15 GHz, 361 angles, automatic CPU settings and a 12 GiB cap. The baseline restored the seven saved pre-construction modules in an isolated package. Construction records are counted only from the canonical execution-system list, and workers saved source hashes. Historical trial directories were not overwritten.

| Run | Version | Solve time (s) | Peak process-tree private memory (GiB) |
|---|---|---:|---:|
| 1 | Current | 115.377 | 2.736 |
| 2 | Pre-check baseline | 115.572 | 2.723 |
| 3 | Pre-check baseline | 115.360 | 2.762 |
| 4 | Current | 115.564 | 2.686 |

Mean total solve time was **115.470 s current versus 115.466 s baseline**, a **0.004 s / 0.0035%** difference. This is effectively a tie at the precision justified by two repetitions. It supports negligible net overhead on this case; it does not establish a universal under-1% bound or a meaningful four-millisecond cost estimate.

Factorization itself averaged **17.656 s current versus 16.045 s baseline** (+1.612 s, about 10.0%). Other stages offset this in the total, including compressed assembly (68.377 versus 69.840 s) and spool reads (0.274 versus 1.455 s). Stage timers are nested/overlapping and must not be summed. The experiment measures the net effect of the current implementation against the saved baseline; individual stage differences should not all be attributed causally to the checks.

All four runs certified on **14,295 nodes**, exited normally, and produced **bit-for-bit identical VV and HH fields**. Each current run recorded **9 construction records and 16,122 checks**: 1,163 live checks plus 14,959 bounded observation reuses. No trial resource guard fired. Peak private memory was comparable; this study does not demonstrate a RAM reduction. The 14 GiB process-tree and 2 GiB host-reserve guards belong to the trial harness, not new solver policies.

`verify_final.py` passed: production source hashes stayed unchanged throughout validation, the restored baseline hashes matched, the companion parser remained byte-identical, all test outcomes were non-failing, and all four field arrays matched. See `verification.json`, `source_hashes.json`, and `confirmation/summary.json`; raw per-run metadata, fields and logs are under `confirmation/runs/`.

## Recommendation

Keep the corrected checks and stop tuning their total runtime for now. The false-refusal fix improves admission correctness without adding work to successful cheap admissions. The measured net overhead is negligible for this inlet, while the checks retain their resource-accounting benefit.

The remaining studies are numerical: coated-inlet conditioning/rank and magnetic-material discretization/forecast scaling. These results do not qualify those cases or establish that every 12-foot material geometry fits 32 GiB. Compressed remains default, dense and impedance remain explicit overrides, and forecast discounts remain disabled.

The Claude handoff is `Claude_audit/optimization_review_fixes_implementation_20261029.md`. No commit or push was performed.
