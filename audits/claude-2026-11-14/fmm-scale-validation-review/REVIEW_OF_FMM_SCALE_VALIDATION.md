# Review of `HANDOFF_FMM_SCALE_VALIDATION.md`

Reviewed: `origin/codex/fmm-scale-validation-2026-11-13` at `90698e9`
(research only; production files identical to `1605874`).
Date: 2026-11-14. All my runs: fresh process per case, `OPENBLAS_NUM_THREADS=1`,
`CPUState(kernel_only=True)`, 4-core Linux container, ~13.3 GiB usable memory
(cgroup limit), run strictly one at a time.

## Verdict

| Handoff claim | My result |
|---|---|
| Contract checks pass | **Reproduced.** `run_checks.sh` rc 0, `check_adaptive_sketch.py` rc 0. |
| Native FMM completes 65,536 unknowns in ~1,540 s / ~4.6 GiB | **Reproduced.** 1,541.0 s, 4.598 GiB (Codex 1,538 s / 4.574 GiB). |
| complex64 preconditioner storage cuts FMM memory at 32,768 | **Reproduced.** 537.7 s, 1.240 GiB, validated. |
| Adaptive sketch makes Compressed 15.8% faster at 32,768 | **Not reproduced.** The difference is timing noise. |
| Adaptive sketch + forecast cap lets Compressed finish 65,536 | Not rerun by me (Codex: 4,161 s / 12.05 GiB). My ablation shows the **cap**, not the adaptive sketch, is what makes it fit. |

Recommendation: keep all of this as research. Nothing here is ready to become
production, and the handoff does not ask for that. The useful conclusion is
about direction: above roughly 32k unknowns the FMM route is the only one that
runs comfortably on this class of machine.

## 1. What reproduces

### Checks
`run_checks.sh` (repairs, norm scope, unseen-component policy, flat near field,
storage contracts, stream validation, native fallbacks) and
`check_adaptive_sketch.py` all exit 0. Logs: `results/run_checks.log`,
`results/check_adaptive_sketch.log`.

### Native FMM, 65,536 unknowns (n=32768, k=640, double preconditioner)

| | Mine | Codex |
|---|---|---|
| Wall time | 1,541.0 s | 1,538 s |
| Peak RSS | 4.598 GiB | 4.574 GiB |

Stage times in my run: loose compressed operator 534 s (3.01 GiB), loose inverse
done at 701 s (4.60 GiB, the run's peak), FMM operators ready at 1,294 s, first
angle solved at 1,393 s.

Accuracy: exact-row backward error over 320 sampled rows, per angle,
1.4e-18 and 2.3e-18. My field agrees with Codex's FMM field to 1.3e-16 and with
Codex's adaptive Compressed field to 3.1e-13 (density 3.3e-11).

### Mixed-storage FMM, 32,768 unknowns (complex64 preconditioner operator)

537.7 s, peak 1.240 GiB, GMRES 45 and 50 iterations, validation passed (rc 0).
Exact-row backward error (192 rows) 2.7e-18 and 4.8e-18. Field agrees with my
Compressed result to 3.4e-13 and with Codex's same run to 7.2e-16.

So at 32,768 unknowns the FMM route takes the same time as Compressed
(~500–540 s) with 38% of the memory (1.24 vs 3.24 GiB).

## 2. The 32k adaptive-sketch speedup is noise

Codex reports Compressed assembly dropping from 448.3 s to 373.2 s with the
adaptive sketch. My four runs of the same case:

| Run (32,768 unknowns) | Wall | Assembly | Factor | Peak |
|---|---|---|---|---|
| Production | 535.8 s | 473.5 s | 58.1 s | 3.24 GiB |
| Production, repeat | 503.9 s | — | — | 3.24 GiB |
| Adaptive, cap 256 | 541.4 s | 473.2 s | 63.6 s | 3.24 GiB |
| Adaptive, no cap | 492.6 s | — | — | 3.24 GiB |

(Earlier sessions measured the production case at 437 s and 504 s.)

Evidence that the patch cannot be responsible for a 15% change at this size:

- My adaptive run's sketch statistics and output fields are **bit-identical** to
  Codex's archived adaptive run, and my production fields are bit-identical to
  theirs. We executed the same arithmetic; only the clocks differ.
- The cap never fired (`capped_calls = 0`, largest forecast 233 < 256), so
  capped and uncapped runs are bit-identical to each other.
- Only 88 of 507 selections used a reduced sketch, and the largest QR
  (1,092 rows) is unchanged.
- Production assembly 473.5 s vs adaptive 473.2 s in back-to-back runs.
- Identical production runs vary by ±8–10% on this host (437–536 s).

The adaptive result differs from production by 1.4e-13 in the field, so the
patch is harmless at 32k. It is simply not a measurable speedup there.

## 3. At 65k the forecast cap is what matters

Codex measured adaptive + cap 256 at 65,536 unknowns (4,161 s, 12.05 GiB) and
stopped the production run at 4,065 s / 13.14 GiB. They did not separate the
two changes. I ran adaptive sketch **without** the cap:

- Killed by the container's memory limit after 4,886 s at 13.3 GiB, with no
  result (`results/adaptive-no-cap-65536.time`, `.oom.txt`).

That is no better than production. So the adaptive sketch alone does not rescue
Compressed at 65k; the initial forecast cap does (Codex's run recorded 22
capped calls with original forecasts up to 2,174). This is a single censored
run, so it does not say how far from finishing the uncapped run was.

Even with the cap, Compressed degrades sharply from 32k to 65k (about 8× time
and 3.7× memory for 2× unknowns), while FMM grows about 2.9× in time. At 65k
FMM is 2.7× faster and uses 38% of the memory.

## 4. Review notes on the code

- `adaptive_sketch.py`: the logic is sound. The first pass still uses the
  forecast, later passes use `max(2*width, width+64)`, and workspace follows the
  new sketch. It works by string-replacing the source of
  `hm.cross_approximation`, which is acceptable for research but must be
  re-implemented properly, with its own tests, if it is ever promoted.
- `_initial_skeleton_factor` (8 when the smaller dimension ≥ 8,192) and the
  forecast `3*prev_max_rank+8` are tuned on one geometry family. I did not test
  the threshold.
- FMM peak memory is set by the loose preconditioner (operator + inverse), not
  by the FMM operators. The complex64 packing addresses the right term; the
  inverse is the next one.
- The repaired exact-row batching fixes the MemoryError I reported above
  ~21,800 unknowns; validation ran at 32k and 65k without it.

## 5. Disclosures and limits

- **Lost summaries.** My timing wrapper overwrote the summary JSONs of the
  mixed-storage 32k and FMM 65k runs with empty files. The wrapper is fixed.
  Wall time, peak memory and stage logs were unaffected; I recomputed the
  exact-row errors and field comparisons from the saved arrays
  (`results/cross_checks.txt`). Iteration counts for the 65k run are therefore
  not recorded here.
- The memory guard I set (13.2 GiB) did not fire before the kernel killed the
  no-cap run; the outcome is the same but the stop was not graceful.
- **Not done:** mixed storage at 65k; Compressed adaptive + cap at 65k (relying
  on Codex's figures); a double-storage FMM 32k rerun; the factor-8 threshold
  ablation; small Dense-referenced storage cases; corners, gaps, layered and
  PEC geometries; many-angle workloads; Windows or another BLAS; the production
  regression suite (production files are unchanged from `1605874`).
- All timings are single runs on a shared host with ±8–10% variation.

## 6. Suggested next steps for Codex

1. Withdraw or re-measure the 15.8% claim with at least three alternating
   runs per variant; report the range.
2. Describe the 65k Compressed result as "forecast cap", and ablate
   cap-without-adaptive-sketch to confirm the sketch change contributes nothing.
3. Run mixed storage at 65k; expected peak is well under 4.6 GiB.
4. Before any promotion, test FMM on a non-smooth case (corner or thin gap) and
   on a many-angle workload, where GMRES cost per angle matters most.

Files: `run_sv.sh`, `timed2.py`, `results/`.
