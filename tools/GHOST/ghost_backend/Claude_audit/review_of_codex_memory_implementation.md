# Review of Codex's memory-accounting implementation (2026-10-29)

Reviewed:
- `Codex_audit/memory_implementation_20261029/`: README, source hashes, validation summary, and the three live 15 GHz results and monitors
- `Codex_audit/claude_memory_review_20261029/`: Codex's response to my last review, and its verification
- The working-tree source on your PC:
  - the new `execution/memory_budget.py` and `execution/memory.py`
  - `compressed/runtime.py`, `factor.py`, `polarization_cache.py` and `retained_storage.py`
  - `twod/solver.py` (the solve limit and per-frequency batch scope)
  - `execution/options.py`
  - `hpc/scheduler.py` and `runs/local_twod_driver.py`
  - `tests/test_request_memory_budget.py`

Everything is still **uncommitted**; GitHub `main` is at `5460aa2`. I read code and saved results only, and ran no tests or solves.

## Verdict

**The implementation is correct, and it fixes the false refusals.** All five memory-audit findings are addressed. The three live 15 GHz runs certify and match their references exactly, with no time or RAM regression. Local runs now get 90% of available RAM.

Codex's corrections to my last review are right, and I accept them below. I found two small accounting leftovers and one bigger limit on the "use 90% of RAM" goal: the 60% storage share.

## Codex's corrections to my review: accepted

| My claim | Codex's correction | Position |
|---|---|---|
| The process baseline (2.35 GiB) and the worker allowance (1.89 GiB) are the two largest terms | The 2.35 GiB already **includes** the 1.89 GiB of workers (`compressed/memory.py:309`). The real non-worker baseline is 0.46 GiB. The non-overlapping terms sum exactly to the 4.55 GiB forecast. | **Accept.** I double-counted. The corrected statement: the worker allowance (1.89 GiB) is the largest single term, larger than the operators (1.02) or the inverse (0.39). It's still the best calibration target, but closing "most of the gap" needs measured per-component data, as Codex says. |
| The operator is "subtracted twice" | The operator is subtracted once, from an allowance that its own allocation had already shrunk. Removing the subtraction would let operator plus inverse exceed the cap. | **Accept.** The fix is a stable allowance, not dropping the subtraction, and that's what was implemented. |
| `HMatrixFactor._refresh_inverse_budget` re-queries available RAM | It reuses the allowance saved at construction | **Accept.** |
| The margins stack | They apply on different paths | **Accept.** |
| The zero-reading fix can wait until late | It should come with the ledger | **Accept.** It now does. |

## Implementation checked against the agreed fixes

| Fix | What the code does | OK? |
|---|---|---|
| **1. Stable storage allowance** | `MemoryBudget.stable()` fixes the ceiling once per request: min(0.9 × initial available RAM, 0.9 × initial Windows commit headroom, explicit cap, scheduler reservation). `automatic_storage_bytes()` now uses that instead of live free RAM. The test reproduces the original case (24 GiB free, 10 GiB operator): storage stays at 12.96 GiB after the operator is allocated, and the inverse gets 2.96 GiB instead of a refusal. | Yes |
| **2. Credit for owned memory** | Operators, factors and worker pools are weakly registered. Later checks allow `credited owned + live available − 10% reserve`. Credit is capped by the process's actual RSS and commit growth, so unrelated growth earns nothing. Workers are credited by unique resident pages (USS), not shared ones. | Yes |
| **3. Spooled payload** | `resident_bytes` excludes bytes on disk. Reloads check the retained-storage cap first, then live headroom before each tile. Failures clear partial tiles and close the spool. | Yes |
| **4. Margins** | The local driver's 75%-of-installed ceiling is now 90% of available (`local_twod_driver.py:98`). The 1.35 planning factor and the 60% storage share are kept on purpose. | Yes |
| **5. Zero vs unknown** | Unknown availability is `None`. A known zero reading can no longer be overridden by an explicit cap. The local scheduler no longer raises a small budget to 1 GiB. | Yes |
| Phase rechecks | `admit_phase('factorization')` and `admit_phase('solve')` re-check live pressure before those phases, and name the binding constraint in the error. | Yes |
| Concurrent requests in one process | Each new request deducts what other live requests have reserved but not yet used. | Yes |
| Per-frequency batch reset (my minor note) | A batch scope per frequency in `_frequency_local_co_solve` (`solver.py:3261`). Polarizations and refinement still share reductions. | Yes |
| Bounded telemetry | `memory_accounting` keeps at most 64 checks and 16 worker samples, on the outer result only. | Yes |

## Evidence checked

| Claim | Check | OK? |
|---|---|---|
| 467 unique test results pass | Validation summary. The one failure (a worker-pipe test that stalled under restricted process access) passed on an isolated rerun and in the broad rerun, and is documented. | Yes |
| Three live 15 GHz runs certify and match exactly | `result.json` for each: quality and mesh certification pass, field difference 0.0 | Yes |
| Constant storage allowance | Codex reports 37, 37 and 24 reads, each constant. Before the fix, the same inlet's allowance drifted from 8.83 to 8.09 GiB over 35 reads. | Yes |
| No regression | Ordinary inlet before vs after the fix: 123.05 s vs 124.02 s, RSS 2.282 vs 2.270 GiB, commit 2.846 vs 2.834 GiB. The narrow inlet (138.6 s) and dielectric inlet (162.9 s) match the earlier compressed runs (137.7 s and 161.1 s). | Yes |

## Remaining issues

| # | Issue | Evidence | Suggested fix | Priority |
|---|---|---|---|---|
| 1 | **The 60% storage share now limits large problems the most.** Retained storage (both operators plus the inverse) is capped at 0.6 × 0.9 = 54% of available RAM. In the test case, 24 GiB free with a 10 GiB operator leaves the inverse 2.96 GiB, while the total limit is 21.6 GiB. For the 15 GHz inlet, the non-storage workspace is about 1.5–2.5 GiB. So on a 32 GB machine, roughly a third of the 90% goes unused whenever the operator is large. | `runtime.py:15`, `automatic_storage_bytes()`; the test at `test_request_memory_budget.py:39` | Size storage per request as the stable reservation minus that request's forecast non-storage workspace (assembly, angle batch, GMRES, workers, baseline), instead of a fixed 60%. The forecast already has those components. Keep 60% as a floor until the near-limit trials pass. | **Next, for the 90% goal** |
| 2 | **Live reload and phase checks still charge untracked process memory twice.** `admit_reload` charges `max(rss, private) + payload` against `credited + available − reserve`. Untracked RSS (the Python, geometry and GUI baseline) is already missing from `available` but is charged again. The excess equals the process's untracked RSS: small in a headless driver, possibly 0.5–2 GiB in the GUI process. Phase checks do the same with the forecast's baseline term (0.46 GiB). It also mixes commit (`private`) into a physical-RAM check. | `memory_budget.py`, `admit_reload` and `limit()` | Check the increment (payload + workspace) against live headroom, and check the total only against the stable reservation. Keep commit in its own check. | Low to medium: only matters near the limit, which is exactly where you want 90% |
| 3 | **Concurrent-request bookkeeping is unsynchronized.** While holding the lock, `stable()` calls other requests' `owned()`. That appends to their worker-sample lists from another thread, and process RSS growth is shared between requests, so credit can be attributed to the wrong request. | `memory_budget.py`, `stable()` and `owned()` | Read the other requests' cached last credit instead of re-sampling them. This is a cosmetic or telemetry risk, not a safety one, since the stable cap still applies. | Low |

Codex already lists the remaining studies honestly: no run filled the machine to 90%, and per-component calibration and concurrent-worker trials are still to come.

## Recommended order

1. **Commit the working tree** (your call). It now holds the compressed default, batch recovery, diagnostic labels and the memory ledger, reviewed by both audits, with 467 tests passing.
2. **Issue #1:** a workspace-based storage share. This is the change that actually unlocks the 90% target for large operators.
3. **Issue #2:** incremental reload and phase checks.
4. A near-limit trial on the 32 GB machine: one large inlet with the storage share from #1, run with your go-ahead.
5. Then calibrate the worker allowance (1.89 GiB forecast vs measured USS, which is now recorded in `memory_accounting.worker_samples`).
