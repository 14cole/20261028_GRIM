# Review of Codex's optimization review fixes (2026-10-30)

Reviewed:
- `Claude_audit/optimization_review_fixes_implementation_20261029.md` (the handoff)
- `Codex_audit/optimization_review_fixes_20261029/`:
  - README, `validation_summary.json` and `verification.json`
  - `full_suite.log`
  - `encoding_changes.json` and `companion_encoding.json`
  - `confirmation/summary.json` and `confirmation/ab.py`
- The local source on your PC, compared with GitHub `6c73ccd`:
  - `execution/memory_budget.py`
  - `tests/test_incremental_worker_memory.py` and `tests/test_source_is_ascii.py`

**Not on GitHub yet:** `main` is still `6c73ccd`. I read code and saved results only; I ran no tests or solves.

## Verdict

**All three changes are correct, and this is the cleanest round so far.**
1. **Refusal recheck fixed.** Codex caught a case I missed.
2. **The full test suite passes:** 2,787 tests and 1,065 subtests, run once without interruption, with only a POSIX-only test skipped. This is the clean full run I asked for before the next push.
3. **The inlet A/B shows the memory checks now cost about nothing in total time** (115.47 s with them, 115.47 s without).

I see nothing blocking a push of everything since `6c73ccd`; that's your call.

## Codex's corrections to my last reviews: accepted

| My claim | Correction | Position |
|---|---|---|
| The exact recheck covers every refusal caused by the cautious worker charge | The old condition (worker RSS greater than worker commit and the modelled overhead) could skip the recheck when the parent process's RSS growth was what bound the reservation. Worker RSS still feeds into that figure, so a false refusal was possible. | **Accept.** Codex reproduced both missed cases in tests. |
| 58,482 construction checks across 21 builds in my first A/B | My script searched the whole metadata recursively and counted the same build records several times, through the channel summaries and shadow copies. The canonical count is 9 builds. | **Accept.** The 12.25 s slowdown I measured stands, because the timings were real. But my check counts and per-check cost were wrong. Codex's copy of the script reads only the execution system's build list. |

## Implementation checked

| Change | What the code does | OK? |
|---|---|---|
| **Refusal recheck** | Whenever the reservation is the binding limit and a cheap worker reading was used, it rechecks once with the detailed scan and fresh live limits. It still refuses if that doesn't fit. No other shortcut condition is involved. Successful admissions keep the fast path. The cost is at most one detailed scan per would-be refusal, which is rare. | Yes |
| **Report note** | Explains that the last 16 worker samples mix detailed and cheap readings, and that a zero unique-residency figure on a cheap sample means "not measured", not zero. Text only. | Yes. This closes my minor note. |
| **ASCII cleanup** | Non-ASCII characters in 9 maintained files are rewritten as escape sequences. Codex verified that every file parses to an identical syntax tree, so the strings the program uses are unchanged, including the GUI text and the material-header aliases. | Yes |
| **ASCII test scope** | Now skips only the top-level `Codex_audit`, `Claude_audit`, `trials` and `scratch` folders, so saved evidence keeps its original bytes. A regression test confirms that similarly named folders *inside* production code (for example `twod/trials/`) are still checked. | Yes |
| Tests | Focused tests: 94 tests and 83 subtests. Full suite: 2,787 passed and 1 skipped, in 20 min 50 s. | Yes |

**One thing to know when you commit:** the ASCII edit also changed `tools/FREDDY/ibc/material_columns.py`, which is **outside GHOST**. It's the twin of GHOST's material parser, and the two must stay byte-identical, which they still are. It parses to the same syntax tree, so FREDDY's behaviour is unchanged. Include it in the same commit so the two copies don't drift apart.

## Fresh inlet A/B

The setup was my script with Codex's counting fix: current, baseline, baseline, current, with the automatic profile and a 12 GiB cap. Here "baseline" means the original code without any of the construction checks.

| Run | Total | Factorization | H-matrix assembly | Linear solve | Peak private |
|---|---:|---:|---:|---:|---:|
| 1 current | 115.38 s | 17.72 s | 57.92 s | 15.86 s | 2.74 GiB |
| 2 baseline | 115.57 s | 16.13 s | 58.05 s | 15.88 s | 2.72 GiB |
| 3 baseline | 115.36 s | 15.96 s | 58.40 s | 15.86 s | 2.76 GiB |
| 4 current | 115.56 s | 17.60 s | 58.17 s | 15.89 s | 2.69 GiB |

- **Total: a tie** (+0.004 s on average). All four runs certified, and the fields are bit-for-bit identical.
- **Factorization is consistently about 1.6 s slower with the checks** (17.6–17.7 s against 16.0–16.1 s, in both pairs). That's the real cost of the checks. It doesn't show in the total, probably because stage timers overlap and this sits inside the run-to-run noise of about 0.2 s. So the honest summary is **at most about 1.6 s, or 1.4% of the solve, and possibly less.** That's under the 2% target either way.
- **Progress across rounds:** +12.3 s for the first version, then +3.7 s, now about 0–1.6 s.

## Small notes (none blocking)

- **The A/B harness lives in two places:** my `Claude_audit\inverse_checks_ab\ab.py` still has the double-counting bug, and Codex's fixed copy is in `confirmation\`. Use Codex's copy for any future A/B. I'll treat mine as superseded.
- **The cleanup script logged a PowerShell warning.** Codex verified independently that only the three intended temporary folders were removed. Fine.

## Recommendation

1. **Push everything since `6c73ccd`**, including the FREDDY parser twin, when you're ready. It's your call, and it's now backed by a clean full suite and a tied A/B.
2. **Stop tuning the memory checks.** What's left is numerical work: conditioning and rank on the coated inlet, and discretization or forecast scaling on the magnetic case, where the surface-impedance override remains the practical route.
