# Review of Codex's large-geometry audit and implementation (2026-10-29)

Reviewed: `Codex_audit/large_geometry_ram_speed_audit.md`, `large_geometry_20261029/` (inlet benchmarks, forecasts), `large_geometry_implementation_20261029/` (patch to 12 files, measurements, validation reports), and the edited source files on the PC. Code reading and checking of the result files only; I did not rerun tests or solves.

## Verdict

The implementation is sound and the reported numbers match the raw result files. I found no blocking bugs. There are four small code issues and one test-environment issue worth fixing. The most valuable next steps are a run-wide "use the tighter inverse" hint and a loss-aware rank forecast. Note that none of this work is in Git yet: GitHub is still at `7a853d8`.

## Accuracy check of the claims

| Claim | Raw files | OK? |
| --- | --- | --- |
| Inverse upgrade: 57.12 s to 44.60 s (21.9%) | `measurements.json`: 57.116 / 44.604 s | Yes |
| GMRES columns 301 to 0; peak RSS +22 MiB | 301 / 0; 1.486 / 1.508 GiB | Yes |
| Batch 128 saved 182 MiB | 1.508 to 1.329 GiB | Yes |
| Upgraded inverse 151 to 179 MB per polarization | 151.4 / 178.9 MB | Yes |
| Field change from upgrade 9.6e-12 | 9.59e-12 | Yes |
| 202 unique tests passed | Latest result per test passed; 13 earlier failures in two runs | Yes, but see the test-environment issue below |
| "Automatic mode, 3.1 GiB budget" run | Its execution options record `factorization: compressed` | Probably the resolved choice, but the file doesn't show it came from Automatic |
| Metal inlet 10 GHz: 5,736 unknowns; narrow inlet 10,563 | Matches the audit tables | Yes. My audit estimated about 8,000 for a metal inlet at 10 GHz, so the two agree |

All performance results are single runs or pairs on one machine. Codex says so; treat the 21.9% as one case, not a general speedup.

One correction to my own audit that Codex's work supports: the H-matrix *operator* already keeps incompressible interaction lists dense (`DENSE_LIST_FRACTION`). The "rank exceeds 133" failure I flagged comes from the HODLR inverse/tile path (`compress_sampled`), not the operator. My recommendation still applies, but only to that path.

## Code review

| Change | Assessment | Issues |
| --- | --- | --- |
| Inverse upgrade (`compressed/factor.py`) | Correct. The old inverse stays live until the new one succeeds, its bytes are deducted from the new budget, any failure restores it, and cancellation propagates. `inverse()` correctly stops re-trying at 2e-10 once the factor is at 1e-10. | (1) The upgrade flag lives on each factor, so every new factor in a run (each adaptive mesh, each polarization, each frequency) builds at 1e-8, stalls, then rebuilds. Codex's fixed-1e-10 runs took 37.2 s against 44.6 s for the upgrade path. (2) It can trigger during condition-estimate probes in the constructor. That is harmless and probably useful, but it is not documented. |
| GMRES memory term (`compressed/memory.py`) | Correct. It matches the allocation in `_gmres` (basis of n x columns x (restart+1), plus work and Hessenberg arrays). | None |
| Tile fallback admission (`compressed/runtime.py`) | Correct ordering: price first, release idle workers, refuse before starting workers. The resident-memory credit and live-residency adjustment are consistent. | (3) In the paired multi-region and native paths, the admission result is computed but not stored in the operator evidence, unlike the single path. |
| Idle worker release (`worker_pool.py`, `tile_processes.py`) | Correct for the current single-threaded flow. | (4) `busy` is set after `acquire()` and `prepare()`, so there is a small window where another thread could release a pool that is about to be used. Set `busy` inside `acquire()`. |
| Angle-batch recovery (`execution/selection.py`, `options.py`, `adaptivity.py`) | Correct: halves down to 1, reprices cached forecasts, uses one common batch across frequencies, and propagates the batch to execution and adaptive steps. | (5) No floor and no time awareness: batch 1 means 361 separate solve passes, which could be much slower without warning. The lost "Formulations: ..." text in the refusal message is a minor regression. |
| Test changes | The two GMRES tests now deny upgrade headroom so they still exercise GMRES. That is legitimate. New tests cover failure, refusal, restart, batch recovery, busy pools and fallback pricing. | None |

**Test-environment issue.** The HPC driver tests failed in two of five runs and passed only once the harness moved `TEMP` into the workspace and forced UTF-8. The underlying failure was hidden by a log-decode error. The likely cause is the Windows directory rename in `hpc/runtime_snapshot.py:86` (`os.rename`), which antivirus and indexing tools often block briefly. A real desktop user can hit this, so retry the rename on `PermissionError` rather than relying on the harness setting.

## Accuracy of Codex's audit conclusions

These all hold up:
- A 12 x 3 ft metal inlet is easy (1.3 to 1.7 GiB at 10 GHz).
- Concavity is handled.
- Refinement can grow the system 3.3x past the first estimate.
- Near-field storage dominates the high-contrast operator (274 of 379 MiB).
- Assembly, not factorization, is where compressed spends its time.

One finding deserves more weight than the audit gives it. The geometry-only rank model forecast an inverse rank of **1,129** for the high-contrast inlet at 1 GHz; the measured rank was **95 to 96**, about 12x lower. The forecast uses the absolute wavenumber and ignores material loss, which strongly damps interactions in lossy media. That one gap probably explains most of the 2x to 3x memory over-forecast we have seen. It also makes the "rank 3,246 / 10,656 exceeds 2,048" warnings at 3 and 10 GHz unreliable.

## Improvements to build on, ranked

| # | Improvement | Why | Effort |
| --- | --- | --- | --- |
| 1 | **Run-wide tight-inverse hint.** After the first accepted upgrade in a run, start later factors (next adaptive mesh, other polarization, other frequencies of the same geometry) at 1e-10 if memory admits. | Codex's own data: fixed 1e-10 at 37.2 s against 44.6 s with upgrade, a further 17% on this case | Small |
| 2 | **Loss-aware rank forecast.** Use the attenuation (imaginary part of k) in the rank model, or calibrate each run's ranks from the existing pilot lists (`compressed/pilots.py`) before admission. | Forecast rank 12x too high on lossy material, which causes refused runs and false "rank exceeds" warnings. Directly answers the earlier request for accurate RAM estimates. | Medium |
| 3 | **Show a refinement range in the preview.** Report the initial forecast plus a likely final range (refinement grew systems up to 3.3x). | The first estimate is not a completion guarantee | Small |
| 4 | **Batch floor and time warning.** Stop halving at about 16 unless explicitly allowed, and record the predicted extra time. | Batch 1 could turn a 1 min solve into a much longer one without warning | Small |
| 5 | **Windows-safe directory rename** with retry and backoff in `hpc/runtime_snapshot.py`. | Removes the failure the test harness worked around | Small |
| 6 | **Record fallback admission in paired-path evidence; set `busy` in `acquire()`.** | Consistent evidence; closes the race window | Small |
| 7 | **Reciprocal H-matrix queries** (both audits agree) | Assembly dominates compressed time (38.8 of 59 s on the 12 ft airfoil) | Medium |
| 8 | **Near-field leaf size and admissibility tuning** for high-contrast bodies | Near blocks are 72% of that operator | Medium, needs measurement |
| 9 | **Commit the working tree to Git** (now two rounds of uncommitted edits) | Review, revert and traceability | Trivial |

Codex did not adopt three of my earlier suggestions: the cavity condition-gate override, a global forecast discount and a fixed 6,000-unknown crossover. Its reasons are fair. Item 2 above is the principled version of the forecast fix, rather than a blanket discount.
