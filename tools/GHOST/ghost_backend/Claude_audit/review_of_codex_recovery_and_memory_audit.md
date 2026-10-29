# Review of Codex's compressed memory recovery and memory-estimation audit (2026-10-29)

Reviewed:
- `Codex_audit/compressed_recovery_20261029/` (README, hashes, interrupted-run note, diagnostic derivative)
- `Codex_audit/memory_estimation_20261029/` (README, `live_summary.json`, `evidence.json`, verification)
- The working-tree source on your PC against `5460aa2`, in particular:
  - the new `execution/angle_batch.py` and `execution/diagnostics.py`
  - the changes to `cpu.py`, `options.py`, `frequency_sweep.py`, `timing_history.py`, `twod/solver.py` and `twod/adaptivity.py`
  - the compressed storage, factor and scheduler code that the memory audit cites

Everything is still **uncommitted**: GitHub `main` is at `5460aa2`. I read code and saved results only; I ran no tests or solves.

## Verdict

**The recovery fix is correct.** It closes all five items both audits agreed on.

**The memory-estimation audit is accurate.** I confirmed its main bug in the source. It is the most useful finding of this round, because it explains refusals while RAM is still free.

I'd add two points:
1. The new batch recovery inherits one of the accounting bugs.
2. In the live run, the RAM over-estimate comes mostly from two terms that are not the matrix or the inverse.

## Part 1: compressed recovery and diagnostics

| Agreed fix | What the code does | OK? |
| --- | --- | --- |
| Memory-only recovery for fixed compressed | `angle_batch.recover` runs only when `factorization == 'compressed'`, at the solver's admission gate, before assembly. It releases idle workers, reprices against the live limit, and halves the batch until it fits or reaches 1. No backend change, no retry after factorization. The batch feeds `_estimate_memory_gb` (`solver.py:1580`), so the repricing is real. | Yes |
| Applied per actual mesh | Called inside the per-polarization, per-mesh solve path. Later refined meshes are re-checked. | Yes |
| Admitted batch reaches parallel workers | `_plan` stores the admitted batch, and the worker caps its options to it. A fixed request whose own backend doesn't fit is deferred to the parent instead. | Yes |
| Driver comments | Both now say compressed is the default and dense is the manual override. | Yes |
| Diagnostic labelling | `mark_uncertified` copies the metadata, sets every certification flag to false, and keeps the originals under `diagnostic_*`. Timing history ignores relaxed or diagnostic runs. The original 105 evidence files are untouched; a corrected derivative sits alongside. | Yes |

Tests: 233 tests and 37 subtests passed. One interrupted run was a test-isolation mistake (a mock leaking between modules), not a production fault. It's documented and was rerun clean.

Two minor notes:
1. **The reduced batch never grows back within a request.** Once a large mesh cuts the batch to 64, every later solve in that request keeps 64 (`state['limit']` only shrinks). That's fine for adaptive refinement, where meshes only grow. For a direct multi-frequency call that runs high frequencies first, the smaller later frequencies run with an unnecessarily small batch: slower, never wrong. GUI sweeps run each frequency as its own request, so they aren't affected. Low priority.
2. **Recovery inherits accounting bug #2 below.** On a later polarization or refined mesh, the gate compares the *total* forecast against *remaining free* RAM, without crediting what the solve already owns. Recovery can therefore shrink the batch, or refuse, because of that accounting error rather than real pressure. Since the reduction then persists for the request, the whole run gets slower. Fixing #2 fixes this too.

## Part 2: memory-estimation audit

| Codex finding | My check against the source | Position |
| --- | --- | --- |
| **1. The automatic inverse-storage cap shrinks after the solve's own allocations, and the operator is subtracted twice.** | Confirmed. `automatic_storage_bytes()` is 0.6 × `_solve_memory_limit_gb()`, which is 0.9 × *currently* available RAM (`runtime.py:24–31`, `solver.py:1513–1514`). `CompressedFactor` recomputes it at construction time, after the operator already uses RAM, then subtracts `operator.bytes` and the reserved partner again (`factor.py:40–43`). `HMatrixFactor._refresh_inverse_budget` does the same. Codex's table checks out: with 24 GiB free and a 10 GiB operator, the constructor raises "No compressed inverse storage remains" even though RAM is free. | **Agree. This is the top fix.** |
| 2. Later gates compare a total forecast with remaining free RAM; `reusable_dense_bytes` credits only dense matrices | Confirmed. It returns 0 unless `factor_mode() == 'dense'` (`session.py:76`). | Agree. Also affects the new batch recovery, as above. |
| 3. Spooled (on-disk) partner bytes still count against RAM | Confirmed. `store_tile` writes the arrays to disk but keeps them in the operator's byte count (`polarization_cache.py:27–38`). | Agree. Admit the reload just before loading, rather than simply subtracting. |
| 4. Stacked margins: the local driver uses 75% of installed RAM, plus 1.35x, 1.25x, the 20% admission margin, and 480 MiB per worker | `_MEMORY_HEADROOM = 0.75` and `_MEMORY_SAFETY = 1.35` confirmed (`local_twod_driver.py:97–100`). | Agree. Don't remove them all at once. |
| 5. A zero available-RAM reading combined with an explicit cap returns the cap | Confirmed (`solver.py:1512`: `... if available > 0 else value`). | Agree. Distinguish "zero free" from "probe failed". |
| Proposed fix: one request-owned memory ledger, admitting the *additional* need, with a 90% ceiling snapshotted once | — | Agree with the design and the order. A blanket switch from 60% to 90% would be unsafe, as Codex says. |

### Addition: where the live run's 2x over-estimate actually comes from

The new certified 15 GHz inlet run forecast 4.55 GiB and peaked at 2.28 GiB of measured RAM. Its saved forecast components (`live_summary.json`) break that down:

| Forecast component | GiB |
| --- | ---: |
| Process and geometry baseline | 2.35 |
| Retained tile-worker allowance | 1.89 |
| Resident operators (both polarizations) | 1.02 |
| Inverse construction | 0.64 |
| Angle-batch work | 0.69 |

These components overlap by phase, so they don't add up to the total. Even so, the two largest terms are the process baseline and the worker allowance (480 MiB plus payload per worker). Neither depends on the matrix or its rank. The measured inverse was 0.24 GiB against a 0.39 GiB forecast, much closer.

So for metal bodies, the quickest gain in estimate accuracy is measuring the process baseline once at start-up, and charging live workers' actual memory instead of a fixed allowance. That would close most of the 2x gap with no change to the rank model. For material bodies, the rank over-estimate found earlier still applies on top.

## Recommended order

1. **Commit the current working tree.** The compressed default and recovery are reviewed and agreed by both audits. That's your call, and it's a clean point to commit from.
2. **Memory accounting fix #1:** snapshot the inverse-storage allowance once per request and stop subtracting the operator twice. Small change, and it removes false refusals.
3. **Fix #2:** admit the additional need, with credit for memory the solve already owns, using one request ledger. That also stops recovery from shrinking batches for no reason.
4. Forecast calibration: measured process baseline and actual worker memory first, then the rank model.
5. Fix #3 (spooled partner admitted on reload), the zero-RAM-reading fix, and clearer refusal reasons.
6. Only then, Codex's near-90% trials on the 32 GB machine.
