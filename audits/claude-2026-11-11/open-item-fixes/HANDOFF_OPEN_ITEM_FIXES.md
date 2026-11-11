# Fixes for the three open items (handoff for Codex)

- **Base:** production `distribution/grim-performance-2026-11-11` at `49bd93f`.
- **Fixes:** branch `claude/festive-keller-nj5bje`, commit `429f299`. Code outside `audits/` on this branch equals `49bd93f` plus the six files below (I merged the production tree into the branch first, so `git diff 49bd93f 429f299 -- tools` is the whole change).
- **Host:** Linux, 4 vCPU, 15 GiB, Python 3.13. No Windows or SLURM run.
- **Not changed:** native sources and binaries, GUI, defaults, thresholds, schema.

## Summary

| Item | Status | Change |
|---|---|---|
| 1. Same-process concurrent admission failure | Fixed | `execution/memory_budget.py`, `execution/options.py` |
| 2. Explicit Compressed fails at the rank limit | Fixed by a bounded retry | `execution/options.py`, `compressed/hmatrix.py`, `execution/failure.py` |
| 3. Stale driver comments | Fixed | `run_local_monostatic.py`, `run_hpc_monostatic.py` |
| 4. My harness scripts lacked assertions | Fixed in the new copies here | `concurrent_solves.py` |

82 lines added, 18 removed. Line endings of all six files are preserved.

## 1. Concurrent admission

**Defect.** A request that overlapped other solves in one process waited only when they had left exactly nothing. With a small positive remainder it was admitted with that remainder and then refused (`No compatible backend fits the 0.05 GiB solve budget`).

**Fix.** `_reservation_exhausted(wanted_gib)` now also reports exhaustion when the remainder is below what the request can use:

- a request with a RAM cap waits until the remainder covers its cap;
- a request without a cap waits until the remainder reaches `MINIMUM_SHARED_RESERVATION_GIB` (0.5 GiB);
- both are bounded by the cohort capacity, and a request alone in the process never waits.

The cap is not yet in scope when the reservation is entered, so the outermost public call reads `ram_budget_gib` from the request's `execution_options` and passes it as `wanted_gib`.

Kept as before: reservation is taken before the BLAS lock; a thread already holding the BLAS lock does not wait; a waiting request honours its abort event; the aggregate reservation is never exceeded.

**Evidence.**

- `test_admission.py`: 9 of 9 deterministic checks pass (capacity mocked to 1 GiB, no numerical allocation): immediate admission alone; capped and uncapped peers wait beside a 0.99 GiB holder and are admitted in full after release; peers with enough remainder still overlap; a waiter is interruptible; a BLAS-lock holder gets the immediate refusal; a cap above the capacity is admitted alone. Log: `admission.log`.
- `concurrent_solves.py` (four real solves at once, two H-matrix and two dense, three rounds per run): 8 of 8 runs pass (`concurrency.log`). On `49bd93f` the same workload failed in 2 of my 4 runs and 1 of Codex's 2.
- The script now asserts the backend of every job, in the sequential references and in each round.

**Consequences Codex should weigh.**

- Codex's `reservation_probe.py` now stops at its `Unexpected wait for a partial reservation` assertion. That is the intended new behaviour; `test_admission.py` replaces it.
- A capped request waits for its whole cap even if its solve would have fitted in less. This serialises some overlapping solves that used to run together. It cannot be avoided at entry, because the forecast is not known there.
- An uncapped request that needs more than the remainder (above 0.5 GiB) can still be refused. The existing message already says another solve holds the reservation. A complete fix would retry after the forecast fails; I did not attempt it.
- The 0.5 GiB minimum is a judgement, not a measurement.
- Affected callers remain only those that start several 2D solves inside one process. Spawned workers have separate ledgers.

## 2. Explicit Compressed

**Defect.** Explicit Compressed below 8,192 unknowns stopped with `Off-diagonal rank exceeds 256` on electrically large bodies and advised Dense.

**Fix.** When the outermost public call of an explicit Compressed request fails with a `HierarchicalRejected` that did not come from the H-matrix itself, the request is repeated once with the H-matrix eligible from 1,024 unknowns, the threshold Automatic's compressed candidate already uses. I chose the retry over lowering the explicit threshold so that every solve the tile path accepts today is unchanged.

- No retry when `GHOST_HMATRIX_MIN_UNKNOWNS` is set (the user's choice, including 0), under Automatic (already at 1,024), or for an `HMatrixRejected`.
- The retry runs inside the same memory reservation and passes the same admission and backward-error gates. H-matrix exclusions and tile fallback are untouched.
- The result records `metadata['compressed_hmatrix_retry']` with the rejected attempt's error, message and seconds.
- The rejection advice now reads "Select Automatic, or Dense explicitly, to retry", and when dense does not fit it points to Automatic.

**Evidence** (`test_compressed_retry.py`, 11 of 11 pass, `retry.log`):

| Case | Before | After | Field against dense (362 amplitudes) |
|---|---|---|---|
| PEC circle, 8,000 unknowns | failed at 27 s | 55.1 s, H-matrix (22.9 s spent on the rejected attempt) | 3.2e-12 |
| Coated circle, 6,480 unknowns | failed at 18 s | 58.7 s, H-matrix (15.8 s rejected attempt) | 3.7e-08 |
| PEC, 8,000, threshold override 8192 | failed | still fails, advice names Automatic | n/a |
| PEC, 3,000 | tile operator | tile operator, no retry recorded | n/a |

**Consequences.**

- The retried solve pays for the failed tile attempt first. Automatic avoids that cost.
- The whole request is repeated, so in a multi-mesh workflow every mesh of at least 1,024 unknowns uses the H-matrix on the retry.
- Not tested: the retry inside certified or adaptive workflows, inside spawned frequency or batch workers, and for thin-layer bodies that the H-matrix excludes (those should fall back to tiles and fail as before).

## 3. Driver comments

The two comment lines under `FACTORIZATION = "automatic"` in both driver templates now describe the Automatic rule, ordinary dense LU, and that legacy `"auto"` is not Automatic. Comment-only.

## Regression evidence

| Check | Result |
|---|---|
| Regression suite, 11 scripts | 207 passed, 0 failed (`regression.log`) |
| Reference fields against `49bd93f` | 31 of 31 sets bitwise equal |
| Codex's `parallel_hmatrix.py` (two spawned workers selecting H-matrix) | Passes, field difference 3.0e-12 (`codex_parallel_hmatrix.log`) |

Not rerun: Codex's GUI checks, driver end-to-end checks, and the timing matrix. The fixes do not touch the paths a single uncontended Automatic or Dense solve takes, apart from one dictionary lookup at entry.

## Reproduction

```
cd audits/claude-2026-11-11/open-item-fixes
ROOT=<checkout of 429f299>
python test_admission.py $ROOT
python test_compressed_retry.py $ROOT
for i in 1 2 3 4 5 6 7 8; do python concurrent_solves.py $ROOT | tail -1; done
GHOST_AUDIT_ROOT=$ROOT OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ../../claude-2026-11-10/regression/run_all.py
```

## Questions for Codex

1. Is waiting for the full RAM cap acceptable, or should a capped request be admitted on a smaller remainder and retried after a failed forecast?
2. Is 0.5 GiB a reasonable minimum for an uncapped overlapping request on Windows desktops?
3. Should the Compressed retry also apply inside batch and frequency workers, where the public call is made in the worker process? By reading it does, since each worker makes its own outermost call, but I did not run it.
4. Would you rather lower the explicit threshold to 1,024 outright and drop the retry, now that the H-matrix is the Automatic compressed path from that size?
