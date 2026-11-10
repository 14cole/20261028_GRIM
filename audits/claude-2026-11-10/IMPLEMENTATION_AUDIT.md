# Implementation audit: fixes from the GHOST 2D/BOR solver audit

For review by Codex. This document describes what was changed in the solver, why each change takes the form it does, the evidence for it, and what was deliberately left alone.

- **Base:** `f207c61` (main).
- **Branch:** `claude/festive-keller-nj5bje`.
  - `62e47e2` — correctness and robustness fixes with their regression scripts.
  - `ceaf233` — two performance changes, calibration data, evidence, documentation.
- **Findings referenced:** IDs from `SOLVER_AUDIT_2D_BOR.md` as amended by `audits/claude-2026-11-09/RESPONSE_TO_CODEX.md`.
- **Environment:** Linux x86-64, 4 vCPU, Python 3.13, NumPy 2.4.6, SciPy 1.17.1, native kernels built locally with gcc 13. Idle host for all timings.
- **Solver diff:** 20 files, 642 lines added, 127 removed. No C source was changed, so the shipped Windows DLLs and the hashes in `NATIVE_LIBRARIES.json` still match their sources.
- **Line endings:** each touched file keeps the line endings it had at `f207c61` (most are CRLF; `bor/factor.py` is mixed and was patched at byte level).

## Status after Codex's review (2026-11-10)

Codex reviewed this document at `1a6adde` (`audits/codex-2026-11-10/` on branch `codex/claude-implementation-review-2026-11-10`) and requested four changes. All four reproduce; see `RESPONSE_TO_IMPLEMENTATION_REVIEW.md`. Read the body below with these corrections, and do not merge the branch until they are addressed.

- **R-1:** the queuing fix can deadlock when the caller already holds the BLAS lock from an outer `execution_scope(limit_blas=True)`.
- **R-3a:** a pool that breaks during `submit()` still aborts the sweep.
- **S-5:** the coarse near-kernel level can be published 16 times outside the 2e-8 tolerance at unprobed points (k = 80 fixture). The default should return to fine publication.
- **S-1, S-2:** `calibration/w_far_rule.py` as committed no longer measures orders below the production table; the table itself is supported by Codex's independent grid.

## Result in brief

| Measure | Value |
|---|---|
| Regression checks on this branch | 191 pass in 11 scripts (`evidence/regression_after.txt`) |
| Same scripts on unmodified `f207c61` | 9 of 11 scripts fail (`evidence/regression_before_f207c61.txt`) |
| Fields after the correctness commit, 31 reference sets | bit-identical to `f207c61` (`evidence/golden_base_vs_correctness_fixes_only.txt`) |
| Fields after both commits | changed by at most 3.1e-12 (2D) and 1.6e-13 (BOR) (`evidence/golden_base_vs_final.txt`) |
| 2D dense solve time, four bodies | 16 to 20% lower; 2.7× lower with one sliver panel |
| BOR operator time, eleven bodies | 4 to 18% lower on ten; one small case unchanged |

The two scripts that pass on the unmodified solver are the analytic baseline (expected) and the S-5 script, whose checks compare two modes of a switch the old solver ignores.

## How to re-run

```
python tools/GHOST/ghost_backend/twod/assembly/native/build.py
python tools/GHOST/ghost_backend/bor/native/build_kernel.py
python audits/claude-2026-11-10/regression/run_all.py                    # about 9 minutes on 4 cores
GHOST_AUDIT_ROOT=/path/to/f207c61/checkout python audits/claude-2026-11-10/regression/run_all.py
python audits/claude-2026-11-10/regression/golden.py <checkout> out.npz   # then --compare a.npz b.npz
python audits/claude-2026-11-10/calibration/w_far_rule.py                 # about 15 minutes
python audits/claude-2026-11-10/calibration/bor_near_publish.py
python audits/claude-2026-11-10/calibration/bench_2d.py <checkout> 3
```

`GHOST_AUDIT_ROOT` points the regression scripts at another checkout; that checkout needs its own built `.so` files.

## Disposition of findings

| ID | Status | Where | Regression script |
|---|---|---|---|
| C-1 | Fixed | `twod/solver.py:1237` | `test_c1_te_open_conductor.py` |
| C-2 | Fixed | `linalg/dense.py:297, 312` | `test_c2_nonfinite_gate.py` |
| C-3 | Fixed | `linalg/onenorm.py` (new), `twod/solver.py:585`, `compressed/factor.py`, `compressed/hmatrix_factor.py`, `bor/factor.py` | `test_r2_c3_linear_algebra_state.py` |
| C-4 | Fixed | `bor/solver.py:5188-5206` | `test_c4_bor_mode_extension.py` |
| C-5 | Guarded, not cured | `twod/geometry.py:2392`, `twod/solver.py:1167-1193` | `test_c5_long_panels.py` |
| R-1 | Fixed by queuing | `execution/memory_budget.py:398-440`, `execution/options.py` | `test_r1_concurrent_solves.py` |
| R-2 | Fixed | `linalg/workspace.py:245`, `linalg/hierarchical.py`, `compressed/inverse.py`, `linalg/refined_lu.py` | `test_r2_c3_linear_algebra_state.py` |
| R-3a | Fixed | `execution/frequency_sweep.py:312` | `test_r3a_worker_death.py` |
| R-3b | Fixed | `twod/solver.py:3344` | `test_r3_input_and_warnings.py` |
| R-3g | Warning added | `twod/solver.py:1196-1234` | `test_r3_input_and_warnings.py` |
| R-3l | Fixed | `linalg/hierarchical.py:44-56` | `test_r3_input_and_warnings.py` |
| M-1 | Finding corrected; telemetry fixed | `twod/solver.py:2599-2606` | `test_r3_input_and_warnings.py` |
| S-1, S-2 | Implemented with calibration | `twod/operators.py:2050-2110, 3266-3273` | `test_s1_s2_w_far_rule.py` |
| S-5 | Implemented with calibration and a switch | `bor/kernels.py:1720-1775` | `test_s5_bor_near_publish.py` |
| Everything else | Not implemented | see "Not implemented" | — |

---

## Correctness changes

### C-1. TE open TYPE 2 conductor

**Change.** `_assert_supported_te_type2_contours` no longer returns early when the scene contains non-conductor elements. It counts the geometric degree of every element end over all non-sheet elements and refuses when a TYPE 2 end has degree 1.

**Why this form.** Codex asked that a broader degree count be tested against partial coatings, sheet mixtures and touching ends before merging. Counting over all non-sheet elements is what keeps a partial coating legal: its bare TYPE 2 arc meets a TYPE 3 cap and the TYPE 4 core arc at each junction (degree 3). Counting TYPE 2 elements only, as before, would refuse it.

**Alternative rejected.** Pinning the free edge unknowns in the sheet + conductor system would make that one scene solvable, but the multi-region scene has no correct single-layer representation of a screen at all. Refusing both is consistent with the documented rule and with the already-refused lone strip.

**Evidence** (`test_c1_te_open_conductor.py`, 17 checks):

| Scene | TE result |
|---|---|
| dielectric + open strip: co-polarised, single-polarisation, certified, bistatic | refused |
| TYPE 1 sheet + open strip | refused |
| coated body + open strip | refused |
| strip from a dielectric vertex with one free end | refused |
| strip ending on a dielectric face | refused earlier by the intersection preflight |
| dielectric + thin closed plate | solves |
| partial coating with TYPE 2/3/4 junctions | solves |
| PEC\|IBC contour stitched from two segments with different flags | solves |
| sheet + separated closed PEC; dielectric alone; coated PEC; closed PEC | solve |

TM on the dielectric + open strip scene still solves and agrees with the thin plate to 0.063 dB.

**Checked and corrected during implementation.** A conductor strip attached to a closed body at both ends (a handle) has degree 3 at each end and would pass this count. It never reaches it: the material-region check refuses the scene first. I had drafted a documentation sentence saying it was undetected, tested it, and replaced the sentence.

**For review.** Are there legal scenes where a TYPE 2 end of total degree 1 is physically closed? I found none; a TYPE 2 end touching only a TYPE 1 sheet is already refused elsewhere.

### C-2. Nonfinite solution passing the dense gate

**Change.** In `DenseFactor.solve`, a column whose residual maximum or denominator is nonfinite gets error `inf`, and a nonfinite solution raises a specific error before the gate.

**Why this form.** My first proposal replaced the whole expression with `np.where(...)`; Codex showed that rejects A = I, b = 0. This version keeps the existing `den > 0` and `den <= 0 & ri > 0` logic untouched and adds one line after it, so ri = den = 0 still yields 0. `np.fmax` is not used.

**Evidence** (`test_c2_nonfinite_gate.py`, 9 checks): zero column, zero matrix, diagonal-with-zero and a 3×3 zero system are rejected; A = I with b = 0, a random matrix with b = 0, and a zero column among non-zero right-hand sides are accepted with x = 0 and error 0.0; a regular system is unchanged (backward error 3.8e-16); a vector right-hand side keeps its shape.

**Not changed.** `twod/fields.py` still accumulates residual maxima with Python `max`; with the gate fixed a NaN can no longer reach it. `bor/factor.py` already had the finiteness check.

### C-3. Condition estimate and the global random generator

**Change.** New module `linalg/onenorm.py`: a block 1-norm estimator (Higham and Tisseur, Algorithm 2.4) written for this purpose with its own `RandomState`. `_deterministic_onenormest` now calls it; the compressed, H-matrix and BOR compressed paths, which called SciPy's estimator directly, do too. The global reseed, its lock and its fork hook are removed.

**Why this form.** Codex asked for determinism without a process-global reseeding race. SciPy's estimator draws from the global generator and offers no way to pass one, so any wrapper around it has to touch global state. A private implementation does not.

**Evidence.**
- Over 300 random real, complex, inverse and BEM-like operators the private estimator equals SciPy's under the former fixed seed bit for bit, is always a lower bound of the exact 1-norm (minimum ratio 0.79), and leaves the global generator position unchanged.
- Dense-path condition numbers are therefore unchanged.
- The C-3 fixture (`audits/claude-2026-11-09/fixtures/fixture_c3_condition_seed.py`) now prints HH 726.34091 for every seed on the tile backend, equal to dense LU; before it printed 706, 706, 676, 676, 733, 216.
- `test_r2_c3_linear_algebra_state.py` asserts seed independence, an untouched global generator, and compressed/dense agreement to 1e-6 (measured 1e-14) on a 600-unknown version.

**For review.** The implementation applies the parallel-column resampling only when the sign matrix is real, as the published algorithm specifies. Bitwise agreement with SciPy on real cases suggests the draw order matches, but an independent reading of `linalg/onenorm.py` against the paper would be worthwhile.

### C-4. BOR mode-cap extension

**Change.** In `_converged_disjoint_batch`, when `mode_start > 0` each pair gets a reference scale from its two lowest modes (one extra coarse evaluation with `m_max = 1`), and `block_error` scales each component by the larger of the band's own maximum and that reference.

**Why this form.** A build from mode 0 scales each component by its maximum over all modes, which the low modes dominate. The extension band alone has no such anchor, so near an axis tip it compared rounding noise with itself. Recomputing the whole band from mode 0 on extension would also work but discards the incremental design; the reference costs one low-order evaluation per pair.

**Evidence** (`test_c4_bor_mode_extension.py`): the cone-cylinder at `mode_tol=1e-13` completes with automatic modes, uses the same 20 modes as an explicit cap of 31, and agrees with it to 5.2e-14. Default tolerance is unaffected (1.7e-9 dB from the tight run). A PEC sphere through the tight-tolerance path stays within 0.008 dB of Mie.

**For review.** Modes 0 and 1 are assumed to be representative of a component's scale. For a pair whose low modes vanish by symmetry while high modes do not, the reference would be too small and the old behaviour (a possible false non-convergence, never a false acceptance) would return. I could not construct such a pair.

### C-5. Electrically long panels

**Change.** Two guards, no quadrature change:
- `_build_panels` refuses `N = -1, -2, -3` while `enforce_mesh_density` is on, with the same four-panels-per-wavelength floor explicit positive counts already had.
- A warning is recorded when any panel exceeds |k|L = 3 (possible only with the floor off, as in exploratory runs).

**Why no quadrature fix.** Making the S/K' far rule and the touching rule accurate for long panels needs subdivision of touching pairs and a new calibration at |k|L up to 40. With the floor closed, no enforced mesh reaches that regime, so the risk did not justify changing the near and touching rules in this pass. This is a guard, and the finding stays open for unenforced meshes.

**Evidence** (`test_c5_long_panels.py`, 11 checks): N = -1..-3 refused; N = -4 and N = 0 accepted without a warning; with enforcement off N = -1 and N = -2 solve and carry the warning on both channels; N = -3 (|k|L = 2.1) carries none.

**Behaviour change.** Inputs with N = -1, -2 or -3 that used to run now raise. Their results were more than 30 dB wrong at oblique angles in my check, so I judged refusal correct, but it is a compatibility break.

---

## Robustness changes

### R-1. Overlapping in-process solves

**Change.** `memory_budget.scope()` waits, before constructing its request, while another request of the process holds (or is about to take) the whole cohort capacity. It wakes when a request leaves or takes a capped reservation, and raises `InterruptedError` if the caller's `abort_event` is set while waiting. `configured_execution` passes the event through.

**Why this form.** Codex asked that any fix preserve the aggregate reservation guarantee. The first request's ceiling is the full capacity, already promised, so a second request can only be given memory by shrinking the first one's promise. I did not want to change the meaning of a held ceiling in accounting code I cannot test on Windows. Queuing changes no reservation arithmetic. It also matches what the default path already did by accident: it serialises on `_BLAS_LOCK`.

**Placement.** The wait is at scope entry, before any solver lock, because a waiter that already held `_BLAS_LOCK` could deadlock against a running solve that takes that lock briefly in `linear_algebra_threads`. A request counts as holding everything from enrolment until its first `stable()` call, which closes the race between two requests starting together.

**Evidence** (`test_r1_concurrent_solves.py`, 9 checks): three direct, four default and four mixed concurrent solves all succeed with the serial answer; a waiting solve raises `InterruptedError` once its event is set (the wait polls every 0.2 s); the running solve is unaffected; no request stays enrolled after success, abort or an input error.

**Behaviour change.** Concurrent in-process solves now run one after another unless caps leave room for both. Requests with explicit caps that fit together still overlap.

**For review.** A public solve called from a worker thread of another solve would wait for its own parent. I found no such call in the package (frequency sweeps use processes; nested public calls run in the caller's context and reuse its scope).

### R-2. Global warning filters

**Change.** New `strict_lu_factor` (LAPACK `getrf`, raising `LinAlgError` on a zero pivot). The three `warnings.catch_warnings()` + `simplefilter('error')` blocks are replaced by it; the mixed-precision cast uses `np.errstate` and the existing nonfinite check.

**Compatibility.** Every caller that caught the escalated warning also catches `LinAlgError` (checked by grep over every `except` site that names `RuntimeWarning`), so fallback chains behave as before.

**Evidence** (`test_r2_c3_linear_algebra_state.py`): `strict_lu_factor` equals `scipy.linalg.lu_factor` bit for bit; singular blocks and an overflowing single-precision cast raise `LinAlgError`; mixed-precision refinement still reaches 3e-15; three threads building four hierarchical factors each leave `warnings.filters` unchanged while a fourth thread's warning is never turned into an exception.

### R-3a. Dead frequency worker

**Change.** `compute_parallel` catches `BrokenProcessPool` per future, defers that frequency, stops submitting, and lets the existing sequential path in the parent finish the rest, exactly as it already did for a worker `MemoryError`. The count is reported as `units_lost_to_worker_failure`.

**Evidence** (`test_r3a_worker_death.py`): with one worker killed by SIGKILL mid-sweep, the sweep completes, reports the loss, returns all 152 samples in the sequential order, and equals the sequential sweep exactly.

### Smaller items

| ID | Change | Evidence |
|---|---|---|
| R-3b | Repeated angles are refused at the top of the four co-polarised entry points, before any work. The single-polarisation diagnostic API still accepts them. `[0, 360]` is still accepted. | six entry-point cases refused in under 1 s each |
| R-3g | A scene of conductors that contains a closed contour but is solved without the combined potential carries a warning. Physics unchanged. | closed + open strip warns; open strip alone and closed body alone do not |
| R-3l | `GHOST_HIERARCHICAL_MIN_UNKNOWNS` raises a named error for non-integer or negative values. | `abc` and `-5` refused by name |

---

## A finding I got wrong: M-1

Both audits reported the dense memory forecast as too low by one matrix and concluded that concurrent planners could over-admit. Codex measured a ratio of 1.366 at N = 6144 against the 1.35 batch margin.

Those measurements were all taken on standalone runs with the whole machine as the limit. Sweep workers and batch units run under a reservation, and the paired assembly that creates the third matrix is admitted only if estimate + partner fits the limit in force. Measured at N = 4096 (estimate 0.67 GiB, partner 0.25 GiB):

| Reservation | Paired assembly | Peak RSS |
|---|---|---|
| none | yes | 0.88 GiB |
| 0.83 GiB (1.25 × estimate) | declined | 0.41 GiB |
| 0.90 GiB (1.35 × estimate) | declined | 0.63 GiB |
| 0.93 GiB | yes | 0.66 GiB |

Peak memory stayed inside the reservation in every reserved case. The forecast is the peak without pairing, and pairing is opportunistic within the limit. No forecast change was made.

What was wrong is the telemetry Codex identified: the `paired_polarization_assembly` record logged the estimate without the partner as `total_peak_gib`. It now logs estimate + partner, with the estimate kept as `solve_estimate_gib`.

**For review.** I tested one size and one formulation. The claim rests on `plan_paired_assembly` being the only source of the third matrix; a reviewer may want to confirm that at N ≥ 6144 under a 1.35× reservation.

---

## Performance changes

Kept in a separate commit from the correctness fixes, as Codex asked.

### S-1 and S-2. Graded far order for the hypersingular block

**Change.** For the linear basis, the far order of W in a tile comes from a table indexed by the tile's largest |k|L and smallest centre separation, instead of a uniform 8. The caller's default order (8) is no longer a floor by itself; an explicitly higher order still is. The mesh-wide eligibility test now admits length ratios down to 1e-6 and |k|L down to 1e-8 (were 1e-3 and 1e-4). Polynomial degrees 2 and 3 keep 9 points.

**Calibration** (`calibration/w_far_rule.py`, output in `w_far_rule.out`). The completed Maue block from the production assembly at q points is compared with the same block at 48 points. Grid: |k|L in {1e-4, 0.01, 0.15, 0.5, 1, 1.5, 2, 3}; arg k in {0, -20, -45, -70, -89.9}°; length ratio in {1, 0.5, 0.1, 0.01, 0.001}; separation in {3, 5, 10, 30} panel lengths; ten orientations per cell including collinear, broadside and perpendicular. Error is the largest entry difference relative to the largest entry of the converged block.

Worst error at separation 3 (the hardest):

| \|k\|L | 5 pts | 6 pts | 7 pts | 8 pts |
|---|---|---|---|---|
| 0.15 | 8.5e-12 | 6.1e-14 | 6.8e-16 | 5.1e-16 |
| 0.5 | 4.3e-11 | 3.0e-13 | 2.4e-15 | 5.9e-16 |
| 1.0 | 3.3e-10 | 2.3e-12 | 1.8e-14 | 1.4e-15 |
| 1.5 | 4.1e-9 | 2.8e-11 | 2.1e-13 | 3.2e-15 |
| 3.0 | 5.7e-7 | 4.8e-9 | 3.5e-11 | 2.7e-13 |

Chosen table (order at separation below 5 / below 10 / beyond), with the worst error of each entry:

| \|k\|L bound | Orders | Worst errors |
|---|---|---|
| 0.15 | 6 / 5 / 5 | 6.1e-14, 6.1e-14, 6.8e-16 |
| 0.5 | 7 / 6 / 5 | 2.4e-15, 1.8e-15, 2.1e-14 |
| 1.0 | 7 / 6 / 6 | 1.8e-14, 5.5e-14, 5.5e-15 |
| 1.5 | 8 / 7 / 7 | 3.2e-15, 6.1e-15, 2.7e-15 |
| 3.0 | 8 / 8 / 8 | 2.7e-13, 4.0e-14, 2.3e-14 |

Selection rule: every entry at or below 1e-13, a factor of ten inside the 1e-12 the code's own error bound promises. The last row is the previous uniform rule and is the only one above 1e-13; it was not loosened. One point fewer fails the 1e-13 margin in every entry. This agrees with Codex's observation that six points give about 1e-14 at |k|L = 1 on a circle and 3.9e-10 at |k|L = 3: six is never used at separation below 5 above |k|L = 0.15.

Slivers and low frequency (`w_far_rule_extremes.py`): at length ratios 1e-4 to 1e-6 and |k|L down to 1e-8, the table's orders give errors no larger than on the ordinary grid (worst 1.5e-14). That is the basis for widening the eligibility bounds.

**Note on an existing documentation figure.** `NUMERICAL_METHODS.md` quotes 1.5e-14 as the worst 8-point W error up to |k|L = 3. My grid gives 2.7e-13 there. It is inside 1e-12 either way; the new documentation section says so.

**Assembled-matrix check** (`test_s1_s2_w_far_rule.py`, 36 checks). On a jittered 160-panel ring, and on rings with a 5e-4 and a 1e-5 sliver, for |k|L from 0.05 to 2.5 and arg k of 0, -35 and -80°, the assembled far entries differ from a 48-point assembly by at most 6.6e-14 of the largest far entry. An impedance circle with a sliver matches the analytic series to 5e-5 dB.

**Field changes.** At most 3.1e-12 relative on the 25 two-dimensional reference sets (the largest on a two-layer dielectric with the dense backend; most are below 5e-14).

**Timing** (`evidence/bench_2d_before_after.txt`; one assembly thread, one BLAS thread, dense LU, median of three):

| Case | Before | After | Change |
|---|---|---|---|
| PEC circle, 1600 panels, \|k\|L 0.31 | 5.19 s | 4.16 s | -20% |
| Impedance circle, 1600 panels, \|k\|L 0.31 | 5.52 s | 4.57 s | -17% |
| Impedance circle, 1600 panels, \|k\|L 1.0 | 6.23 s | 5.23 s | -16% |
| Coated cylinder, 800 + 560 panels | 6.35 s | 5.34 s | -16% |
| Impedance circle, 1200 panels, one sliver | 7.59 s | 2.83 s | -63% |
| Impedance circle, 1200 panels, no sliver | 3.35 s | 2.58 s | -23% |

**Interaction left as is.** The TM-reuse path in `formulations/regions.py:474-490` passes `max(obs_order, src_order, floor)` as a minimum far order for its row-strip queries, so that path stays at 8 points. It is still accurate; it just does not gain. Entries obtained through differently shaped queries can now differ at the 1e-13 level for W as they already could for S and K'.

**For review.** (1) Whether a block-relative 1e-13 is the right acceptance measure, given that the existing S table is described as within 1e-12. (2) Whether ten orientations per cell are enough; the five fixed ones were chosen as the usual worst cases. (3) Degrees 2 and 3 were not recalibrated.

### S-5. BOR near angular rule publishes the coarse level

**Change.** In `_refine_near_chunk`, when the stride probes are active the coarse level is evaluated for every point and the fine level only for the probes. If every probe agrees within `NEAR_ANGULAR_RTOL`, the coarse values are published. Otherwise the previous complete check runs. `GHOST_BOR_NEAR_PUBLISH=fine` restores the former behaviour.

**Why a switch.** Codex noted a calibration grid was required before adoption. The switch makes the old values reproducible bit for bit (verified on six bodies, `evidence/golden_base_vs_final_bor_fine_mode.txt`), which gives a rollback and an A/B test with no code change.

**Calibration** (`calibration/bor_near_publish.py`, output in `bor_near_publish.out`; two mode workers):

| Body | Largest probe discrepancy | Operators before → after | RCS change |
|---|---|---|---|
| PEC sphere, ka 3 | 1.6e-12 | 1.95 → 1.74 s | 3.4e-14 |
| PEC sphere, ka 10 | 8.0e-12 | 5.33 → 4.44 s | 5.5e-14 |
| PEC sphere, ka 30 | 1.3e-10 | 23.05 → 19.82 s | 2.7e-14 |
| Impedance sphere 100-150j, ka 6 | 1.9e-12 | 6.45 → 5.58 s | 2.6e-14 |
| Sheet sphere 200+100j, ka 4 | 7.2e-13 | 0.85 → 0.87 s | 1.5e-14 |
| Dielectric sphere 4-0.2j, ka 3 | 1.6e-12 | 3.81 → 3.48 s | 2.8e-14 |
| Lossy dielectric 4-4j, ka 3 | 1.7e-12 | 3.81 → 3.65 s | 7.8e-14 |
| Coated PEC sphere, ka 3 | 1.7e-12 | 6.55 → 5.84 s | 1.0e-13 |
| PEC cone-cylinder, 6 GHz | 8.6e-12 | 10.79 → 8.88 s | 1.4e-13 |
| PEC ogive, 4 GHz | 2.0e-12 | 6.22 → 5.85 s | 1.8e-13 |
| PEC finite cylinder, 5 GHz | 1.5e-12 | 7.08 → 6.24 s | 8.4e-14 |

The acceptance tolerance is 2e-8, so the largest discrepancy seen is 150 times inside it. No chunk fell back. Timings are single runs.

**What the probes do and do not show.** Three quarters of the points in an accepted chunk are published at the coarse level without their own comparison. That was already true of the fine level before this change; the probe now certifies the level that is published. The probe discrepancy grows with ka (1.6e-12 at ka 3, 1.3e-10 at ka 30); it was not measured above ka 30.

**For review.** Whether the trend with ka needs a bound at larger electrical size, and whether the unprobed points warrant a tighter stride now that they carry the published value.

---

## Not implemented

| ID | Reason |
|---|---|
| C-6a | Untested hypothesis; Codex's three high-index disk cases did not show it. |
| C-6b, C-6f | Accuracy limits of weak contrast and very low frequency; no fix designed. |
| C-6c, C-6d, C-6e | Error-accounting and dead-threshold items with no demonstrated wrong result. |
| C-6g | Certification floor is intentional; a reporting change belongs to the certificate text. |
| C-6h | Rounding-level non-reproducibility of BOR far blocks; low severity. |
| C-5 (cure) | Long-panel quadrature; guarded instead, see above. |
| R-3c | Bare automatic profile overriding `OPENBLAS_NUM_THREADS`; a policy decision. |
| R-3e | cgroup CPU quota and nested memory limits; cannot be tested in this environment. |
| R-3f, R-3h, R-3i, R-3j, R-3k | Contract and documentation clarifications. |
| S-3, S-4, S-6, S-7 | Larger restructurings of tile and pair traversal; gains unverified. S-7 must preserve the reciprocity diagnostic. |
| S-4b | Lossy near-table retry at degree 16; not attempted. |
| S-4c | Requires changing `far.c`, which would put the shipped Windows DLL out of step with its source and recorded hash. |
| S-8 | BLAS thread policy for small BOR systems; sub-second effect on an idle host. |
| S-10, S-12, S-14, S-15, S-17, S-18 | Small or environment-specific gains. |
| S-9, S-11, S-13 (speed), S-16 | Withdrawn in the response to Codex. |
| M-2, M-3a, M-3b | Forecast recalibration. Codex cautioned against replacing conservative budgets with observed RSS; needs Windows commit measurements. |

## Behaviour changes a user can notice

- TE solves of scenes with an open TYPE 2 conductor next to a dielectric, coating or sheet now raise instead of returning a wrong field.
- `N = -1, -2, -3` raise while the density floor is on.
- Repeated angles raise immediately on co-polarised entry points.
- A second solve started in the same process waits for the first.
- A singular dense system raises "returned a nonfinite solution" instead of a later amplitude error.
- Compressed-backend condition estimates no longer vary between runs and can differ from previously recorded values (they now equal the dense estimate).
- New warnings: electrically long panels (floor off only); closed conductor solved without resonance protection.
- 2D fields change at the 1e-12 level or below; BOR fields at the 1e-13 level or below.

## Limits of this work

- Nothing was run on Windows. The memory-reservation change (R-1) touches code whose commit-charge branches I could only read.
- The largest systems exercised were 1,600 unknowns (2D timing) and 300 elements (BOR calibration).
- Timings are from one 4-core virtual machine; 2D figures are medians of three, BOR figures are single runs.
- The regression scripts are plain Python scripts under `audits/`, not part of a test suite, because this distribution ships none.
- `NUMERICAL_METHODS.md`, `BOR_PERFORMANCE.md` and `GEOMETRY_INPUT_CHEATSHEET.md` were updated to describe the changes.
