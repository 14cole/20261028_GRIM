# Review of Codex's memory follow-ups (commits 63429ba and b233c19, 2026-10-29)

Reviewed:
- `Codex_audit/claude_implementation_review_20261029/`: Codex's review of my last audit, with its counterexamples
- `Codex_audit/memory_followups_20261029/`: README, validation summary, the four live 15 GHz runs, and the two real-memory ramps
- The diff of `b233c19` in:
  - `execution/memory_budget.py`
  - `compressed/runtime.py` and `compressed/memory.py`
  - `twod/solver.py` and `twod/formulations/thin_layer.py`
  - `hpc/scheduler.py`
  - `tests/test_memory_followups.py`
- `ui/solver.py`, to see whether the GUI can run two solves in one process

GitHub `main` is now at `b233c19`. It holds the compressed default, batch recovery, diagnostic labels, the memory ledger (`63429ba`) and these follow-ups. I read code and saved results only; I ran no tests or solves.

## Verdict

**The follow-ups are correct.** All three issues from the last round are fixed:
- shared-process credit
- reload and phase double-charging
- the fixed 60% storage share

The new storage sizing is the change that matters most for your 90% goal. On a 32 GB machine with about 28 GiB free, a large inlet now gets about 22 GiB for stored matrix data instead of about 15 GiB.

Two new findings matter more than any remaining code issue:
1. **On your PC, Windows commit limit is tighter than physical RAM.** It was 14.6 GiB of commit headroom against 16.7 GiB of free RAM. That, not the solver, is now what stops you reaching 90%.
2. **The new live runs are about 25% slower than the previous round's**, with identical numerics. It is most likely other work running on the PC at the same time, but it is unproven.

## Codex's corrections to my last review: accepted

| My claim | Codex's correction | Position |
|---|---|---|
| Everything was uncommitted at `5460aa2` | `63429ba` was already on GitHub when I reviewed | **Accept.** My check was stale by minutes. |
| Concurrent-request bookkeeping was a cosmetic risk | Two overlapping requests could both claim the same RSS growth. Its counterexample admitted 30.6 GiB of reservations against a 21.6 GiB target. Caching credit, as I suggested, wouldn't fix that. | **Accept.** This was a real safety bug, not a cosmetic one. |
| Non-storage workspace of 1.5–2.5 GiB | It is 3.145 GiB for the solve phase. I had corrected my local copy, but the version on GitHub still has the old figure. | **Accept.** |
| Keep 60% as a storage floor | A floor can exceed a known requirement: with a 10 GiB budget and 6 GiB of workspace, a 60% floor grants 6 GiB and totals 12 GiB | **Accept.** It should be a fallback, not a floor, which is what was implemented. |
| A GUI baseline of 0.5–2 GiB | Not measured in any trial | **Accept.** It was an estimate. |
| Reload double-charging was low to medium priority | Codex reproduced two concrete false refusals, including one that compared private commit with physical RAM | Agree. It was worth fixing now. |

## Implementation checked

| Fix | What the code does | OK? |
|---|---|---|
| **Shared-process reservations** | Each request joins a locked group when it starts, before its first forecast. The group's total capacity is fixed by the first request (90% of physical RAM or commit, whichever is lower). Later requests get only what's left. Once two requests overlap, both stop getting in-process RSS credit for the rest of their lives; only separately measured worker processes still count. No request samples or changes another's telemetry. The regression gives 12 + 9.6 + 0 GiB. | Yes |
| **Reload checks** | `require_reload` checks the *additional* payload against live physical headroom and against live commit headroom separately, each in its own units. Total request usage is checked only against the stable reservation. The existing process baseline is no longer charged as a new allocation. Both of Codex's false-refusal reproductions now pass, and each real-pressure refusal still fires. | Yes |
| **Phase checks** | Only the forecast's interpreter baseline (128 MiB), up to what was actually measured at entry, is credited as already present. Geometry and cache allowances are still charged in full. Measured payload above the forecast raises the requirement. | Yes |
| **Workspace-based storage** | Payload allowance = stable reservation − the largest phase's non-storage forecast. I checked that the non-storage terms don't depend on the allowance (`compressed/memory.py:265`), so the two-pass forecast can't exceed its own reservation. 60% is used only when no forecast exists. Hierarchical forecasts reserve paired-assembly workspace either way, and the speculative-vs-active plan split and the analytic-zero cleanup are both tested. | Yes |
| Tile fallback | Records the largest of its forecasts as the active envelope | Yes |
| Diagnostics | Errors name what set the stable reservation (for example `initial_commit_headroom`) and label reload amounts as additional | Yes |

**Does the same-process rule hurt GUI users?** No. The GUI runs one job at a time (`_job_is_active`, `ui/solver.py:851`), and separate frequency workers run in their own processes with scheduler caps. So the conservative rule (no in-process credit once requests overlap, and a later uncapped request gets nothing) only affects scripts that run two public solves in parallel threads. That's an acceptable trade-off.

## Evidence checked

| Claim | Check | OK? |
|---|---|---|
| 391 unique tests pass, 24 of them new | Validation summary. Early failed development runs are kept and labelled. | Yes |
| Four live 15 GHz runs certify and match exactly | `result.json` for each | Yes |
| Same numerical path as before | Identical preconditioner tolerances and refinement counts in all three repeated cases (inlet, narrow, dielectric) | Yes |
| Commit-limited ramp | 16.67 GiB of free RAM but only 14.59 GiB of commit headroom, so a 13.13 GiB reservation. It touched 13.07 GiB, then correctly refused another 0.125 GiB. | Yes, and reported honestly as not a 90%-of-physical result |

### Timing: about 25% slower, and probably not the code

| Case | Previous round (`63429ba`) | This round (`b233c19`) |
|---|---:|---:|
| Ordinary inlet | 124.0 s | 155.8 s |
| Narrow inlet | 138.6 s | 173.4 s |
| Dielectric inlet | 162.9 s | 192.0 s |

The ordinary-inlet slowdown is spread evenly across stages:
- kernel assembly ("operators"): 65 → 83 s
- factorization: 14 → 18 s
- linear solve: 15 → 18 s

Every adaptive step is slower, including the first, small mesh. Kernel assembly doesn't touch the memory code, and the numerics are identical. That pattern points to other work on the PC during the trials, which Codex discloses.

One part is probably real, though small. At the 6 GiB cap, the final mesh now gets *less* storage than before (2.86 vs 3.6 GiB), and spool writes went from 5 to 11 (2.6 → 5.7 s). See finding 2 below.

To settle it: two quiet back-to-back runs of the ordinary inlet at 6 GiB, one on `63429ba` and one on `b233c19`, about 5 minutes in total. I'd only run that with your go-ahead.

## Findings

| # | Finding | Evidence | Suggestion | Priority |
|---|---|---|---|---|
| 1 | **Windows commit limit, not the solver, now caps you below 90% of physical RAM.** Commit headroom is free RAM plus pagefile room, minus what's already committed. Windows charges commit when memory is allocated, not when it's touched. These runs also commit about 25% more than their RSS (2.83 vs 2.27 GiB). So on this PC, commit runs out first. | Ramp: 14.59 GiB commit vs 16.67 GiB physical. The reservation was set by `initial_commit_headroom`. | **Your call:** a larger or system-managed Windows pagefile raises commit headroom without using more physical RAM. Codex rightly didn't change any OS setting. The other route is reducing commit-only allocations, which needs profiling first. | **High, if 90% matters** |
| 2 | **The worker allowance now directly reduces storage.** It is still a fixed 1.89 GiB forecast of the 3.145 GiB non-storage total. With a big reservation that barely matters (25 − 3.1 ≈ 22 GiB of storage). With a small cap it's worse than the old 60% (2.86 vs 3.6 GiB at 6 GiB), which costs some spooling. | Trial table, "payload allowance across meshes" | Calibrate the worker allowance from the measured worker USS, which is now recorded in `memory_accounting.worker_samples`. This was already next on both audits' lists. | Medium |
| 3 | **Overlapping requests in one process lose all in-process credit.** That brings back the original "total vs remaining free" behaviour for their later polarizations. | `owned()` and `baseline_credit()` once `shared_process` is set | Fine for now, since the GUI serializes jobs. Revisit only if scripted multi-threaded solves become a real use. | Low |
| 4 | The 391 results are a targeted subset, not a rerun of the full 467 from last round | Validation summary file list | Run the full suite once before the next push | Low |

## Recommended order

1. **Decide on the pagefile.** It's the cheapest way to get past the 79–80% you can reach now. Windows' "system managed size" is usually enough.
2. **Quiet A/B timing rerun** (2 runs, about 5 minutes, needs your go-ahead), to confirm the 25% slowdown is host contention.
3. Calibrate the worker allowance from the measured USS. This is now the main lever on storage at small and medium caps.
4. Then a real near-90% solve on the 32 GB machine, after #1.
