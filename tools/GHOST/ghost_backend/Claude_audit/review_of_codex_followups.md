# Review of Codex's follow-up implementation (commit 4b0bfba, 2026-10-29)

Reviewed:
- `Codex_audit/response_to_claude_large_geometry_review.md`
- `Codex_audit/followups_20261029/` (README, measurements, benchmarks, loss study, 15 GHz capacity file, validation results)
- The production diff `bb25908..4b0bfba`, covering `preconditioner_hints.py` (new), `factor.py`, `hmatrix_factor.py`, `memory.py`, `runtime.py`, `tile_processes.py`, `worker_pool.py`, `options.py`, `selection.py`, `adaptivity.py` and `runtime_snapshot.py`

I read the code and checked the reported numbers against the raw result files. I did not rerun any tests or solves.

## Verdict

The work is sound. Every number I checked matches the raw files. I found no correctness bugs in the new code, and the accuracy gates are unchanged. Codex's corrections to my last review are mostly fair, and I accept them below.

The most important point for you is in the 15 GHz section. The two metal inlets are proven at 15 GHz within 32 GB. The dielectric "fits" row is not, and refinement will probably take it well past 32 GB.

## Numbers checked

| Claim | Raw files | OK? |
| --- | --- | --- |
| Learned hint 43.16 s to 38.40 s (11.0%) | `solve_seconds` 43.161 / 38.396 | Yes |
| Peak RSS 1.518 to 1.487 GiB (31.6 MiB less) | Monitor: 1,630,179,328 / 1,596,997,632 bytes | Yes |
| Inverse builds 8 to 5 | `total_factor_build_calls` 8 / 5 | Yes |
| 15 GHz metal inlet: 14,295 unknowns, dense, 103.4 s, 3.971 GiB | Matches | Yes |
| 15 GHz narrow inlet: 15,849 unknowns, compressed, 113.1 s, 4.750 GiB | Matches | Yes |
| Leaf 64: 202 MiB less RAM, 21.6% slower | 1.290 vs 1.487 GiB; 46.69 vs 38.40 s | Yes |
| Loss study ranks: 198/201, 120/125, 89/90; forecast 967 / 981 / 1,143 | Matches; full-row backward error at most 5.6e-15 | Yes |
| 223 unique tests pass | `validation_summary.json`: 223 / 223, nothing unresolved | Yes |

Two caveats:
- The hint-off baseline was 44.60 s in the previous round and 43.16 s here, on the same case. That is about 3% run-to-run noise, so read the 11% as "about 8 to 14%".
- All timings are single runs on one machine. Codex says this too.

## Where Codex corrected me, and I agree

- **GitHub state.** My "GitHub still at `7a853d8`" was stale by the time Codex read it. That was already fixed in my file.
- **Automatic provenance.** The request does record `adaptive`, and the run resolved to compressed. I missed it.
- **Windows rename.** The saved failures don't prove an antivirus or indexing cause. The bounded retry is still a reasonable hardening step.
- **Loss as the main cause of over-forecasting.** The controlled study shows the lossless case is already over-forecast about 5x in rank and 3.2x in bytes (322 MB forecast against 99 MB measured). Loss adds to the over-forecast but isn't most of it, so I withdraw that claim. The byte ratio is what admission actually uses, and it runs from 3.2x lossless to 8.4x at full loss.
- **The 17% hint gain.** It measured 11%, as Codex warned.
- **Hard batch floor of 16.** Codex is right that a floor would refuse jobs that only fit at small batches. A notice is the better design, and it is now implemented.

## Code review

| Change | Assessment |
| --- | --- |
| Learned tighter inverse (`preconditioner_hints.py`, `factor.py`) | Correct. A hint is learned only after a field solve passes the backward-error bound inside `inverse()`. Each hinted build is checked against both the payload budget and live headroom. Any build failure drops the hint and falls back to the normal 1e-8 path, including its compact fallback. A solve failure on a hinted inverse gets exactly one ordinary rebuild. Cancellation re-raises. State lives only for the request, with at most 16 small records. |
| Condition-probe labelling | Correct. `phase` is now recorded on upgrade events, and `max_refinements` now counts the step discarded by an upgrade restart. |
| Paired fallback evidence (`runtime.py`) | Correct for both the native and multi-region paths. The regional change keeps a rank-rejected pair together rather than dropping to TE only, which is a real fix the new tests found. |
| Worker lease (`worker_pool.py`, `tile_processes.py`) | Correct. One lock covers acquire, release and idle eviction. `busy` is set before `prepare()`, and release runs in `finally` on every path. A second traversal now raises instead of silently sharing. |
| Batch notices and refusal text (`selection.py`, `adaptivity.py`, `options.py`) | Correct. The formulation names are back in the refusal message. The reference-mesh fallback now uses the batch size that was actually admitted, a real bug Codex found and fixed. |
| Forecast loss diagnostics (`memory.py`) | Diagnostic only, with no change to admission. Fine. |
| Windows publish retry (`runtime_snapshot.py`) | Correct. It retries at most 4 times, only on Windows error codes 5, 32 and 33. It rechecks that the destination doesn't exist before each attempt, and re-raises the final error. |

Minor notes, none of them blocking:
1. **Hints are off for multi-frequency calls.** `scope()` enables hints only when the request has exactly one frequency. GUI sweeps run each frequency as its own call (`fresh_sweep` and `frequency_sweep`), so they benefit. A script or HPC run that passes several frequencies in one direct `solve_monostatic_rcs_2d` call gets no hints at all, even within a single frequency's adaptive steps. Re-entering the scope per frequency inside the solver's frequency loop would fix this.
2. **Hint key ignores polarization.** TE and TM share one entry, so the TM build uses TE's bytes as its reference. That is harmless because TE and TM inverse sizes are within 3%, but it should be documented.
3. **Quadratic growth allowance.** Payload is set to twice the old bytes times (n_new/n_old)², so a 3x refinement step needs about 18x the old inverse bytes in headroom. On large cases, that conservatism could refuse the hint exactly where it would help most. Once a few more learned-hint runs exist, log predicted against actual bytes and tighten the allowance.

## Accuracy issue that matters most: 15 GHz on 32 GB

All three adaptive trials grew well beyond the initial candidate meshes:

| Case | Largest initial candidate | Final unknowns | Growth |
| --- | ---: | ---: | ---: |
| High-contrast inlet, 1 GHz | 8,648 | 12,972 | 1.5x |
| Metal inlet, 15 GHz | 4,362 | 14,295 | 3.3x |
| Narrow metal inlet, 15 GHz | 4,815 | 15,849 | 3.3x |

Both 15 GHz metal cases tripled the panel count during refinement. Apply that to the moderate-dielectric 15 GHz scenario: 17,424 initial unknowns would become about 57,000. Dense memory grows with the square of that, so the 8.68 GiB forecast would become roughly 50 to 95 GiB. The compressed forecast would also grow, though by how much is uncertain. Codex's table correctly says this row is "not a final-refinement capacity result". In plain terms, though, a material-filled inlet at 15 GHz should be expected **not** to fit in 32 GB on dense, and to be borderline on compressed.

The metal inlet results stand: 4 to 5 GiB with plenty of margin.

The preview should show this. Codex now labels initial sizes as "not a likely final-size range", which is honest but gives the user no number to plan with. Two-plus cases with the same 3.3x at high frequency are enough for a labelled "if refined about 3x" scenario line in the preview. It wouldn't be a guarantee, and it shouldn't change admission.

## Improvements to build on, ranked

| # | Improvement | Why | Effort |
| --- | --- | --- | --- |
| 1 | **Show a refined-size scenario in the preview.** Report the initial forecast plus a labelled "if refinement triples the mesh" line, for RAM and unknowns. | Above: the dielectric 15 GHz case looks like it fits but probably won't | Small |
| 2 | **Start adaptive meshing finer at high frequency.** Both 15 GHz cases spent two coarse steps before the mesh that mattered (2,908 to 4,362 to 8,592 to 14,295). | Saves the wasted early solves. Needs per-step timings to size the gain; the benchmark files don't record them | Medium |
| 3 | **Re-enter the hint scope per frequency** in the direct multi-frequency loop | Gives script and HPC sweeps the same speed-up as the GUI | Small |
| 4 | **Stop loss from raising the rank forecast.** The forecast uses the wavenumber's magnitude, which grows with loss, while measured ranks fall: 967 to 1,143 forecast against 198 to 89 measured. Using the lossless (real-part) wavenumber, or the lossless forecast as a cap, is still conservative and needs no calibration data. | The forecast moves the wrong way as loss increases | Small |
| 5 | **Pilot-informed "expected" RAM, shown alongside the admission figure.** Operator pilot ranks track loss closely (139 down to 40), and inverse rank was 1.4x to 2.2x the operator rank in every loss case. Show it as an informational estimate; don't use it for admission yet. | Gives a realistic number next to the conservative one (forecast bytes were 3x to 8x high in the loss study) | Medium |
| 6 | **Record per-step adaptive timings** in result metadata | Needed for item 2 and for any time estimate | Small |
| 7 | **Calibration set for the rank model.** Codex's proposal: more geometries, frequencies and withheld cases before changing admission. | The safe route to accurate admission | Large; needs runs |

Codex's decisions not to ship the reciprocal cache (zero hits) or leaf 64 (21.6% slower) are right on the evidence.
