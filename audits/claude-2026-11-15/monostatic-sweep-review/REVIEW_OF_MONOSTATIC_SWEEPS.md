# Review of `HANDOFF_MONOSTATIC_SWEEPS.md`, with repeats, a solver fix and a 32k sweep

Reviewed: `origin/codex/monostatic-sweep-investigation-2026-11-14` at `384db52`
(research only; no production file differs from `1605874`).
Date: 2026-11-15. My runs: fresh process each, one thread, strictly serial,
~13.3 GiB container, Codex's `monostatic.py` harness and supplied research `.so`
(source verified identical to the previously audited one).

## Verdict

I agree with the handoff's decision: for the stated workload (180–360
monostatic angles) keep Dense/Compressed as the production route; FMM remains a
memory-constrained research candidate. The evidence replays exactly and the
checks pass. Three things change or sharpen the picture:

1. **The 43% FMM gain was the stronger preconditioner, not block solving.**
   With the same 1e-4 preconditioner, scalar GMRES beats Codex's block solver
   when it checks the true residual every step.
2. **I found why every block restarts, and a fix.** A right-preconditioned
   block solver that restarts as soon as a true-residual check fails cuts
   accurate operator applications by 31% against scalar GMRES and is the
   fastest FMM variant measured (605 s at 8k, against 991 s scalar on the same
   host).
3. **32,768 unknowns, 180 angles, measured:** Compressed 416 s / 3.71 GiB;
   best FMM 3,944 s / 1.71 GiB. FMM is 9.5× slower with 46% of the memory.
   There is no crossover at 32k for this workload.

## 1. Replay and checks

- `unpack_arrays.py` restored all 58 cases; `analyze.py` on the restored
  evidence produces an `analysis.json` byte-identical to the committed one.
- `check_projection`, `check_batched`, `check_rhs_batching`, `check_block`,
  `check_block_cadence`: all rc 0.
- My Compressed 8k/180 arrays are bit-identical to Codex's. My repeat of the
  block tol-1e-4 case agrees with Codex's field to 7.9e-13 (not bitwise; FMM
  near blocks differ at roundoff across hosts) and my two repeats are bitwise
  identical to each other.

## 2. 8,192 unknowns, 180 angles (star, TE, k=80), FMM preconditioner 1e-4

| Case | Compute s | Solve s | Accurate A applications (RHS-equivalent) | Peak GiB |
|---|---:|---:|---:|---:|
| Compressed, run 1 / run 2 | 39.4 / 43.7 | 3.6 / 4.9 | — | 0.725 |
| FMM block, check every step, run 1 / run 2 | 1,184.5 / 1,178.0 | 1,115 / 1,107 | 8,144 | 0.444 |
| FMM scalar GMRES (full sweep) | 990.7 | 920.7 | 5,669 | 0.436 |
| FMM block, check every 4th step (full sweep) | 860.6 | 788.0 | 5,760 | 0.444 |
| FMM right-preconditioned block, first version | 892.2 | 819.8 | 5,876 | 0.444 |
| FMM right-preconditioned block, width 16, first version | 830.5 | 754.9 | 5,572 | 0.531 |
| **FMM right-preconditioned block, restart on failed check** | **604.6** | **533.8** | **3,884** | 0.443 |

All FMM variants agree with Compressed to 3.3–3.4e-12 in field and 2.4e-11 in
density (max over angles); exact-row backward errors are ≤ 2.5e-15.

Findings:

- **Repeatability.** The two block runs differ by 0.6% and perform identical
  work (same counts, bitwise-identical output). Codex measured 873 s for this
  case; my host is ~35% slower. Work counts, not seconds, should be compared
  across hosts.
- **Attribution.** Scalar GMRES at 1e-4 (991 s) is faster than the per-step
  block solver (1,181 s). Codex's "43.1% better than baseline FMM" is therefore
  a preconditioner-strength effect; block solving with per-step checks is a net
  loss at this size. Codex flagged this as needing the full scalar control —
  this is that control.
- **Cadence.** The 24-angle cadence-4 probe result holds for the full sweep:
  13% faster than scalar, 27% faster than per-step checking.

### Why the blocks restart

I instrumented projected and true residuals (first version of my solver). For
a typical block of eight angles:

| Block step | Projected residual | True residual |
|---:|---:|---:|
| 17 | 6.1e-13 | 4.4e-11 |
| 19 | 1.7e-15 | 3.0e-11 |
| 20 (restart) | 1.8e-15 | 3.4e-11 |
| 30 (second cycle) | 1.3e-17 | 6.8e-16 |

Within one Arnoldi cycle the true residual stalls near 3e-11 while the
projected residual keeps falling. The 1e-12 acceptance target is below what one
cycle can deliver, so a restart from the true residual (one step of iterative
refinement) is always needed. Every block in every block variant used exactly
two cycles (46 cycles for 23 blocks). Extending the first cycle past step ~17
is wasted work.

### The fix (`block_gmres_right.py`)

- Right preconditioning: the Arnoldi residual estimates the original system's
  residual, so no true-residual application is needed until the estimate
  reaches the target.
- When a true check fails, restart immediately from the true residual.
- Acceptance is unchanged: every original RHS must pass the true 1e-12
  residual; duplicate, zero and all-zero RHS tests pass
  (`check_block_right_v2.log`).

Result: 3,884 A applications (31% fewer than scalar, 33% fewer than cadence 4),
605 s compute. It is still 14–15× slower than Compressed at 8k. My first
version (tighten the trigger and continue) gave no gain; it is kept as
`block_gmres_right_v1.py` for the record.

## 3. 32,768 unknowns, 180 angles (star, TE, k=320)

| Case | Setup s | Solve s | Compute s | Peak GiB |
|---|---:|---:|---:|---:|
| Compressed (production) | 386.2 | 28.6 | 415.7 | 3.706 |
| FMM, 1e-4 preconditioner, right block (fixed) | 380.7 | 3,562.5 | 3,943.9 | 1.712 |

- Fields agree to 1.6e-11, densities to 4.3e-11 (max over angles); exact-row
  errors 1.1e-15 and 2.0e-16.
- FMM used 5,900 A applications for 180 angles (32.8 per angle), close to the
  8k count per angle scaled by the weaker relative preconditioner; each
  application costs ~0.55 s.
- Setup times are equal. The whole difference is the solve: 28.6 s against
  3,562 s. To break even at 32k, FMM would need its solve phase cut by more
  than 100×, which no Krylov refinement tested here approaches.
- The stronger preconditioner raises FMM memory from 1.26 GiB (my earlier
  16-angle run at 1e-2) to 1.71 GiB.

I did not run 65k/180. From the numbers above an FMM 65k sweep would take many
hours on this host; Compressed 65k needs ~12 GiB and ~1.7 h here. That
comparison should be made on the user's 32 GB machine with real thread counts,
as Codex says.

## 4. Other review notes

- `block_gmres.py`: correct as written. Deflation at 1e-14 of the block norm
  drops directions without keeping them, which is safe at that threshold.
  Converged columns are not locked, so they keep being iterated; this is a
  further possible saving.
- The 1e-12 tolerance drives the restart behaviour. Production's own solve
  tolerance should be the reference for any future FMM timing; if the gate
  were, say, 1e-10, one cycle would suffice and the ranking of variants could
  change. I did not test other tolerances.
- Rank-scan conclusion (angular RHS sets are full rank at large electrical
  size) is consistent with what I see: block width 16 saved only 5% of A
  applications over width 8 and cost 20% more memory.
- Dense disk/batch and packed-inverse sections: read, not rerun. The handoff's
  own cautions (page-cache effects, no peak reduction) are appropriate.

## 5. Disclosures

- Each case is a single run except the two repeated pairs.
- I stopped two runs deliberately and removed their partial files: the 32k
  Compressed run when I re-ordered the queue (rerun in full later), and a 32k
  FMM run 30 s after launch to switch it to the fixed solver.
- Small unit tests of my solver (seconds) ran during the first 8k block run.
- `monostatic_right.py` is Codex's `monostatic.py` with one import changed.
- Full density arrays for these runs total 734 MB and are not committed.
  `results/fields_and_row_checks.npz` holds every field, angle grid and
  exact-row residual; JSON, timing and stderr records are complete.
- Not done: slot/square geometries with the new solver, TM, 360 angles, 65k,
  thread scaling, shared S/K′ far translation (item 4), inverse packing (item 5),
  layered/PEC cases (item 6).

## 6. Suggested next steps for Codex

1. Review `block_gmres_right.py`; if accepted, make it the FMM research
   default and rerun the slot and square cases with it.
2. Add column locking and test whether the first cycle can stop at a fixed
   projected level (~1e-10) to avoid the one failed check per block.
3. State FMM results against production's actual solve tolerance.
4. Treat the time question as settled for sweeps at ≤32k: Compressed wins by
   an order of magnitude. FMM work is justified only by memory, i.e. sizes
   where Compressed does not fit; measure that boundary on the 32 GB machine.

Files: `block_gmres_right.py`, `block_gmres_right_v1.py`, `monostatic_right.py`,
`run_suite_right.py`, `claude_suite*.json`, `summary.txt`, `field_checks.txt`,
`results/`.
