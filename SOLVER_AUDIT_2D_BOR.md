# GHOST 2D and BOR solver audit — findings for cross-examination

- **Commit audited:** `f207c61` (line numbers below refer to it). Paths are relative to `tools/GHOST/ghost_backend/`.
- **Scope:** `twod/`, `bor/`, `compressed/`, `linalg/`, `execution/`, `runs/` (planning logic only for `hpc/`).
- **Environment:** Linux x86-64, 4 vCPU, 15 GB, Python 3.13, NumPy 2.4.6, SciPy 1.17.1 (OpenBLAS). Native kernels were built locally with gcc 13 from the shipped C sources. The Windows DLLs and all Windows-only branches (commit-charge accounting) were read, not executed.
- **No test suite ships in this checkout**, so every number below comes from tests written for this audit. Nothing in the repository was modified.

## How to read the evidence column

| Status | Meaning |
|---|---|
| **REPRODUCED** | Run twice independently: by a reviewer and again by the lead on a quiet machine. |
| **MEASURED** | Run once by one reviewer; numbers quoted are theirs. Timings taken on a heavily loaded host are marked. |
| **INSPECTION** | Reasoned from the code; not executed. Says what would confirm it. |
| **NOT REPRODUCED** | Claimed by a reviewer, then failed to reproduce on a quiet machine. Listed so the cross-examiner does not rediscover it. |

## Bottom line

1. **One result-affecting defect:** the 2D TE (VV) solve accepts an open TYPE 2 conductor whenever the scene also contains a dielectric, coating or sheet, solves it with equations that cannot represent it, and passes the gate and the mesh-convergence certificate with errors of 3 to 8 dB (C-1).
2. **No other physics error was found.** Every closed-body 2D formulation matched an analytic cylinder series in complex amplitude (1e-9 to 2e-4 relative), every BOR formulation matched Mie to 0.08 dB or better with second-order convergence, and all operator blocks matched independent quadrature to 1e-12 in the supported mesh range. See "Verified correct".
3. **Gate and robustness holes:** a NaN solution passes the dense backward-error gate (C-2); compressed condition estimates depend on the caller's global random state (C-3); the BOR mode-extension retry fails with a misleading error (C-4); two overlapping in-process solves give a spurious `MemoryError` (R-1).
4. **Speed:** assembly dominates everywhere (2D operators about 70% of a dense solve; BOR near-field preparation 83 to 94%). The concrete savings found are 20 to 30% of 2D dense assembly (S-1, S-2) and roughly 15 to 30% of BOR solve CPU (S-5 to S-7).
5. **Memory planning:** the dense forecast is low by one N×N matrix (M-1); the tile-compressed forecast is high by 2 to 2.6× (M-2); the BOR estimate has a 2.8 GB floor (M-3).
6. **A reviewer claim that did not hold up:** "the default compressed path is 5 to 11× slower than dense" was an artefact of the loaded audit host (N-1).

---

## Correctness findings

### C-1. 2D TE: open TYPE 2 conductor in a mixed scene is solved wrongly and certified — CRITICAL — REPRODUCED

- **Where:** `twod/solver.py:1193` (`_assert_supported_te_type2_contours` returns early with `if pol != "TE" or not _is_all_robin(infos): return`); `twod/solver.py:1797-1830` (`_geometric_sheet_endpoint_nodes` pins only `seg_type == 1` ends); `twod/formulations/sheet.py:89,110-112`.
- **Defect:** the open-end refusal only fires when every element is a Robin (PEC/IBC) element. Add any dielectric, coated body or TYPE 1 sheet and an open TYPE 2 strip is accepted for TE.
  - Dielectric or coated body + open strip: the multi-region path puts a single-layer density with a Neumann row on an open arc, which cannot represent the jump of Hz across a screen.
  - TYPE 1 sheet + open strip: the mixed sheet+PEC system is used, but the strip's two edge unknowns are not pinned.
- **Evidence (lead's own run, dense LU, 1.5 GHz, VV in dB at 0/45/90/135/270°):**

  | Scene | N=-20 | N=-60 | Gate |
  |---|---|---|---|
  | dielectric rectangle + open TYPE 2 strip | -13.99, -15.24, -5.17, -15.24, -1.41 | -13.99, -15.24, -5.17, -15.24, -1.42 | passed |
  | same, strip drawn as closed plate 0.2 mm thick | -13.48, -12.41, -2.10, -12.41, -0.44 | -13.48, -12.41, -2.10, -12.41, -0.44 | passed |

  The open-strip answer is mesh-converged and 2.8 to 3.1 dB off at 45°, 90°, 135°. HH (TM) agrees between the two scenes to 0.06 dB. The same strip alone is correctly refused.
- **Reviewer's wider measurements (MEASURED):** `solve_monostatic_rcs_2d_certified` returned `mesh_convergence_certified=True` with a published error estimate of 0.012 dB while VV was off by up to 5.4 dB; `solve_bistatic_rcs_2d_certified` up to 8.6 dB. Sheet (150+60j Ω) + open TYPE 2 strip: up to 7.7 dB; the same strip entered as TYPE 1 with Zs = 1e-7 matched the plate to 0.08 dB.
- **Doc conflict:** `GEOMETRY_INPUT_CHEATSHEET.md` says "A free TYPE 2 end is refused for TE"; `NUMERICAL_METHODS.md` ("TE sheets") says open TYPE 2 strips in sheet scenes "keep the single-potential equations".
- **Repro:**

  ```python
  import sys; sys.path.insert(0, "tools/GHOST")
  from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
  from ghost_backend.twod import solver as S
  def rect(x0, y0, x1, y1):  # clockwise
      p = [(x0,y0),(x0,y1),(x1,y1),(x1,y0),(x0,y0)]
      return "\n".join(f"{p[i][0]} {p[i][1]} {p[i+1][0]} {p[i+1][1]}" for i in range(4))
  head = "Title: t\nSegment: d 3\nproperties: 3 -20 0 1 0\n" + rect(-0.05,-0.03,0.05,0.03) + "\n"
  tail = "IBCS_Resistances:\n\nDielectrics:\n1 3.0 -0.1 1.0 0.0\n"
  strip = "Segment: s 2\nproperties: 2 -20 0 0 0\n-0.05 0.08 0.05 0.08\n"
  plate = "Segment: s 2\nproperties: 2 -20 0 0 0\n" + rect(-0.05,0.0799,0.05,0.0801) + "\n"
  for body in (strip, plate):
      g = build_geometry_snapshot(*parse_geometry(head + body + tail))
      r = S.solve_monostatic_rcs_2d(g, [1.5], [0.,45.,90.,135.,270.],
                                    geometry_units="meters", solver_method="direct")
      print([round(s["rcs_db"], 2) for s in r["samples"] if s["polarization"] == "VV"])
  ```
- **Fix:** run the open-end check for TE regardless of `_is_all_robin`, counting the geometric degree of TYPE 2 ends over all non-sheet elements (so TYPE 2/3/4 partial-coating junctions stay legal). For sheet + PEC, either refuse or pin free conductor ends as sheet ends are pinned.
- **Not tested:** an open TYPE 2 strip that touches a dielectric body.

### C-2. `DenseFactor.solve` accepts a NaN solution and reports backward error 0.0 — MEDIUM — REPRODUCED

- **Where:** `linalg/dense.py:287-294` (`metrics`), `dense.py:310-315`.
- **Defect:** `np.divide(ri, den, out=zeros, where=den > 0)` leaves 0 where `den` is NaN, so the error is 0.0 and passes the 1e-12 gate. `max(prev, nan)` then keeps `max_relative_residual` at 0.0. There is no finiteness check on `x` (`bor/factor.py:349`, `HierarchicalFactor` and `CompressedFactor` do have one).
- **Evidence:** n = 200 random complex matrix with one zero column: accepted, 24 of 600 solution entries non-finite, `max_backward_error = 0.0`, `max_relative_residual = 0.0`. Zero matrix and diagonal-with-zero: accepted, all entries NaN.
- **Mitigation already present:** `_rcs_sigma_from_amp` (`twod/solver.py:881`) rejects non-finite amplitudes, so the RCS paths fail late with a misleading message rather than returning a wrong number. Density-only paths (`project=False`) lack that net; not run.
- **Fix:** `errors = np.where(np.isfinite(ri) & np.isfinite(den) & (den > 0), ri/den, np.inf)`; add a finiteness check on `x`; use `np.fmax` or an explicit NaN test for the running maxima; raise on a zero pivot.

### C-3. Compressed and H-matrix condition estimates depend on NumPy's global RNG — MEDIUM — REPRODUCED

- **Where:** `compressed/factor.py:327,332`; `compressed/hmatrix_factor.py:196`; `bor/factor.py:395`. All call `scipy.sparse.linalg.onenormest` directly. The dense path uses the seeded `_deterministic_onenormest` (`twod/solver.py:599-606`).
- **Evidence:** two PEC circles with a 0.5% gap, 1200 unknowns, 10 GHz, `np.random.seed(1..6)` before each solve. Tile backend HH `condition_est_max`: 706.3, 706.3, 675.7, 675.7, 733.3, 216.3 (spread 3.4×). Dense LU: identical every time. The global generator position moves from 624 to 528, so the caller's stream is consumed.
- **Impact:** a system near the 1e6 gate can pass or fail on unrelated RNG state; estimates can be low by 3.4×.
- **Fix:** route all three sites through `_deterministic_onenormest`. Separately, that helper reseeds the global RNG under a private lock (`solver.py:599-606`); a local `Generator` would avoid disturbing other threads (INSPECTION).

### C-4. BOR automatic mode-cap extension fails with "near meridian quadrature did not converge" — MEDIUM — REPRODUCED

- **Where:** `bor/solver.py:5187-5194` (`block_error` in `_converged_disjoint_batch`), reached through `solver.py:2289-2303` (`mode_start = old_cap + 1`) and the retry in `bor/options.py:273-288`.
- **Defect:** the retry prepares only the missing modal band. The convergence test normalises by the largest block inside that band; near a graded axis tip those high-order blocks are rounding noise, so coarse/fine never agree and a `ValueError` tells the user to refine the mesh.
- **Evidence:** PEC cone-cylinder, 3 GHz, 117 nodes, `mode_tol=1e-13`. Explicit `n_modes=31` succeeds (20 modes used). Automatic modes (cap 19, extended to 31) raise `ValueError: ... elements (0, 2); gap=0.00062113, order=192, relative block change=0.000235`.
- **Exposure:** no failure was found at the default `mode_tol=1e-6` (cap exceeded modes used by 2 to 4 on the cases tried). Any tolerance somewhat tighter than default can hit it.
- **Fix:** carry a reference scale into `block_error` for extension bands (the pair's maximum over the accepted band), or recompute with `mode_start=0` on extension.

### C-5. Electrically long 2D panels: S/K' far and touching rules lose accuracy silently — MEDIUM (latent) — MEASURED

- **Where:** `twod/operators.py:684-695` (touching rule fixed at 20 points), `2022-2047` (`_graded_far_order` capped at 8 above |k|L = 3), `2060-2075` (W floor rises to 16), `3226-3234`.
- **Defect:** the self block and the W far rule adapt to |k|L; the S/K' far rule and the touching rule do not, and nothing warns.
- **Evidence (relative block error vs independent hp quadrature):**

  | \|k\|L | S far | K' far | touching 90° (S) | touching 150° (S) |
  |---|---|---|---|---|
  | 3 | 2e-14 | 6e-15 | 1.4e-14 | 1.8e-13 |
  | 6 | 7e-10 | 1e-11 | 7e-11 | 8e-9 |
  | 8 | 5e-8 | 3e-9 | 7e-9 | 7e-7 |
  | 12 | 3e-5 | 2e-7 | 4e-6 | 4e-4 |
  | 20 | 7e-2 | 1e-4 | 1e-2 | 0.41 |

- **Reachability:** `twod/geometry.py:2390-2415` enforces 4 panels per material wavelength (|k|L ≤ 1.57) unless `enforce_mesh_density` is off, so default runs are safe. Whether the density floor uses Re(k) or |k| in strongly lossy media was not checked.
- **Fix:** scale the S/K' far order with |k|L as W already does and split long touching pairs, or raise when |k|·Lmax exceeds about 4.

### C-6. Lower-severity and unconfirmed correctness items

| ID | Item | Where | Status |
|---|---|---|---|
| C-6a | Dielectric, coated and multi-region BOR solvers start the modal tail at exterior k·ρ only; IBC and sheet solvers add the guided-wave band. A lossless high-ε disk on a whispering-gallery line could truncate early. Spheres cannot show this. Confirm by comparing automatic modes with `n_modes ≈ \|n\|·k·ρ + 10`. | `bor/solver.py:4677, 7226` vs `4313` | INSPECTION |
| C-6b | Weak-contrast 2D dielectric (ε = 1.0001) loses relative accuracy: 5e-5 at ka = 0.01 rising to 7.5e-3 (0.064 dB) at ka = 5, equal and opposite in TE and TM. Normal contrasts give 1e-6 to 2e-5 on the same mesh. | 2D transmission path | MEASURED |
| C-6c | H-matrix far blocks discard the oracle's dropped-route error bounds (about e^-32 ≈ 1e-14 relative), so `row_error` is not the bound the factor assumes. | `compressed/hmatrix.py:693, 1034-1035` | INSPECTION |
| C-6d | Polynomial (degree 2/3) near acceptance test scales S and K' by one common magnitude, so S is tested loosely for small panels. Measured S errors were still 1e-14 to 4e-12. | `twod/polynomial_quadrature.py:140-142, 883-898` | INSPECTION |
| C-6e | `constraint_residual_vec` is computed in every monostatic branch and never used; `constraint_residual_norm_max` is a dead threshold. | `twod/solver.py:2577, 2616, 2689, 2715, 2749` | INSPECTION |
| C-6f | BOR IBC at very low frequency degrades without a warning: 0.11 dB error and 0.19 dB aspect spread at ka = 1e-4. | BOR IBC-CFIE | MEASURED |
| C-6g | BOR certification floors dB and phase 30 dB below the per-frequency peak. A 27→37 element cone-cylinder certified with a 0.62 dB floored delta against 1.77 dB unfloored. The published estimate (1.68 dB) was still conservative; no wrongly certified result was constructed. | `runs/quality.py:23-35, 516-544` | MEASURED |
| C-6h | BOR far blocks are reproducible only to rounding (2.2e-16) when tiles are source-split, because tiles accumulate in completion order. Comments call tile shapes "bitwise-equivalent". | `bor/streaming.py:1786-1792, 1839-1876` | MEASURED |

---

## Robustness findings

### R-1. Overlapping in-process solves: second request gets a 0 GiB limit — MEDIUM — REPRODUCED

- **Where:** `execution/memory_budget.py:134-155, 201-208` (first request's ceiling is the whole capacity; `cohort_remaining_reservation = capacity − Σ other.ceiling`); raised at `twod/solver.py:2528, 3631`.
- **Evidence:** three threads each running a 68-panel `solve_monostatic_rcs_2d(..., solver_method='direct')`: one succeeds, two raise `MemoryError: ... requires an estimated 0.16 GiB, but 15.13 GiB is currently available; the safe allocation limit is 0.00 GiB`.
- **Related (MEASURED):** with the default method the second solve does not fail but waits behind `_BLAS_LOCK` (`execution/options.py:481-483`) for the whole first solve, with no abort check.
- **Fix:** reserve each request's forecast rather than the full limit, or reject concurrent in-process solves with an accurate message.

### R-2. `warnings.catch_warnings()` + `simplefilter('error')` used from worker threads — HIGH if reachable — MEASURED (synthetic), reachability by INSPECTION

- **Where:** `linalg/hierarchical.py:488-490`, `compressed/inverse.py:176-178`, `linalg/refined_lu.py:30-33`.
- **Defect:** `catch_warnings` saves and restores the process-wide filter list and is not thread-safe. Two overlapping blocks can leave a permanent `error` filter, after which every warning in the process raises.
- **Evidence:** three threads each building six `HierarchicalFactor`s (leaf size reduced to widen the window) left `warnings.filters[0] == ('error', ...)` after all threads finished.
- **Reachability:** `bor/solver.py:3093-3098` builds modal factors inside the `ThreadPoolExecutor` at `solver.py:3218`. Not reproduced end to end.
- **Fix:** call LAPACK `getrf` and test `info`, as `bor/factor.py:90` already does.

### R-3. Other robustness items

| ID | Item | Where | Status |
|---|---|---|---|
| R-3a | A frequency worker killed by the OS aborts the whole sweep: only `MemoryError` is deferred to the parent, `BrokenProcessPool` propagates and completed in-memory results are lost. The batch dispatcher does recover. | `execution/frequency_sweep.py:299-309` | MEASURED (SIGKILL) |
| R-3b | Duplicate angles are rejected only after both polarisations are fully solved. `[0, 360]` is accepted and solved twice. | `twod/solver.py:2991-2994`, `twod/samples.py:301` | MEASURED |
| R-3c | Bare automatic requests force `blas_threads='auto'`, overriding a user's `OPENBLAS_NUM_THREADS`; only `GHOST_ASSEMBLY_THREADS` is consulted. | `execution/options.py:545-550` | MEASURED |
| R-3d | Linux native libraries are untracked (`*.so` ignored) and load failure is silent. With loaders forced off, N = 1200 assembly went from 5.7 s to 19.2 s; matrices agree to 5e-16. | `.gitignore`, `twod/assembly/native/{table,far,near}.py` | MEASURED |
| R-3e | cgroup CPU quota is never read (`cpu.max`), and the cgroup memory limit is read only at the mount root, not from `/proc/self/cgroup`. | `execution/options.py:177-215`, `twod/solver.py:1443-1448`, `hpc/scheduler.py:219-222` | INSPECTION |
| R-3f | `mesh_reference_ghz` does not give one mesh across a sweep: a sweep to 3 GHz with reference 1.5 GHz used 348 panels at every frequency, a single 0.8 GHz call with the same reference used 188. The 0.8 GHz VV field differs by 8.8e-4. | `twod/solver.py:3265-3283, 2318-2362` | MEASURED |
| R-3g | Closed PEC + open TYPE 2 strip in TM falls back to the unprotected single-layer system without the warning the sheet branch emits; condition number reaches 2e7 at interior resonances (fields still correct to 3e-7). | `twod/formulations/robin.py:14-22`, `twod/solver.py:2726-2758` | MEASURED |
| R-3h | The public co-polarised 2D API cannot solve an open TYPE 2 strip at all, although the cheat sheet describes a TM-only run. | `solve_monostatic_rcs_2d` | MEASURED |
| R-3i | BOR: `workers=2` still uses 4 near-preparation workers; `workers` is not a CPU ceiling. | `bor/solver.py:625-632` | MEASURED |
| R-3j | BOR: a failure at frequency k discards all completed frequencies unless the caller uses `run_checkpointed`. | `bor/dispatch.py:2195-2760` | INSPECTION |
| R-3k | BOR rejects open TYPE 2 surfaces ("not supported in phase 4") while the same physics runs as TYPE 1 with a zero impedance. | `bor/dispatch.py:259-264` | MEASURED |
| R-3l | `GHOST_HIERARCHICAL_MIN_UNKNOWNS` is read with an unvalidated `int()`; a bad value raises a bare `ValueError` from `DenseFactor.__init__`. | `linalg/hierarchical.py:44-50` | INSPECTION |

---

## Speed findings

All 2D timings below are single-thread unless stated. Assembly dominates: at N = 3000 PEC, dense, 181 angles, operator assembly is 69% of the run, two LUs 15%, RHS solves 6%. At N = 8192, assembly is 70 to 83% for every backend.

### 2D assembly

| ID | Finding | Where | Evidence | Expected gain | Status |
|---|---|---|---|---|---|
| S-1 | W's far floor forces 8×8 points on every far tile whenever W is requested, including S, K', D, where the graded table would use 5 to 7. A uniform 6-point rule changes all four matrices by ≤ 2.6e-14 at \|k\|L = 0.31. | `twod/operators.py:2057, 3231-3234` | N = 1600: far integration 2.7 s → 1.9 s, total 3.8 s → 3.0 s (quiet host) | ~1.4× far pass, ~20% of dense assembly at 20 panels/λ. Calibrate by \|k\|L: 6 for ≤ 1.0, 7 for ≤ 1.5, 8 for ≤ 3. | REPRODUCED |
| S-2 | One sliver panel (< 0.001 Lmax), or \|k\|Lmax outside [1e-4, 3], switches the whole mesh to a 16-point far rule. | `twod/operators.py:2068-2075` | 1200-panel circle: far integration 1.6 s → 5.8 s (3.6×) with one sliver | Avoids 3.6× far-pass penalty on graded or CAD-sliver meshes. Apply the test per tile. | REPRODUCED |
| S-3 | Far order is chosen per tile from its smallest ratio; diagonal tiles compute both orientations. | `twod/operators.py:3219-3230, 3122-3146` | Sample counting: 1.56× the per-pair graded count at N = 2000, 1.19× at N = 6000, 3.75× for a single 190-panel tile | 1.2 to 1.6× on dense far integration | MEASURED (counts, not timing) |
| S-4 | Near pass integrates both (i,j) and (j,i); the adaptive rule calls SciPy Bessel functions instead of the kernel table. | `twod/operators.py:3320-3346, 1626-1658` | Two concentric 700-gons, 0.3h gap: near integration 4.7 s of 8.5 s; 1.5 s in `_stable_hankel2_array` | Roughly halves near integration (10% of total on smooth contours, 25 to 30% on thin layers) | MEASURED (loaded host) |
| S-4b | Near-batch kernel table for lossy media is built at degree 12 only; on rejection it falls back to `hankel2e` (2349 ns vs 139 ns per distance). Rejections were ε = 1-10j, 1-100j, 1-1000j where the true error was 2e-15 to 2e-14. | `twod/polynomial_quadrature.py:412-417` vs `twod/assembly/kernels.py:506-517` | 39 of 48 cases accepted at degree 12, 47 of 48 at 16 | ~17× on near kernel evaluation in conductor-like media | MEASURED |
| S-4c | Native far block evaluates the H1 polynomial even when only S is wanted. | `twod/assembly/native/far.c:73-82, 135` | Patched copy: 39.1 → 31.8 ns/sample, bitwise-identical S | ~20% on S-only and W-only far passes | MEASURED |

### BOR

| ID | Finding | Where | Evidence | Expected gain | Status |
|---|---|---|---|---|---|
| S-5 | Near angular rule publishes the 1.5× "fine" level although the coarse level is already ~1e-12 (tolerance is 2e-8). Cost is 1.75 coarse-units per point. | `bor/kernels.py:1717-1781, 1285-1295` | 300-element sphere, 14 GHz: near kernels 72% of solve CPU. Error vs 3× reference: 7e-13 (G) and 3.5e-12 (MFIE) at coarse, 6e-14 and 1.2e-13 at fine | Publish coarse, probe with fine: ~21% fewer near samples, 13 to 15% of solve CPU | MEASURED |
| S-6 | Near rule fragments into many tiny native calls (8,720 calls, median 60 points). | `bor/kernels.py:1585-1594, 1683-1693` | 4.7 s of 30.1 s near-kernel CPU is Python glue | Up to ~10% of solve CPU; round piece orders to a coarser quantum | MEASURED |
| S-7 | Near EFIE Green blocks are integrated for both (e,f) and (f,e); the far path already uses the symmetry. | `bor/near_storage.py:86-106`, `bor/solver.py:2282` | By inspection; consistent with G points = MFIE points | ~40% of near G work, ~8% of solve CPU | INSPECTION |
| S-8 | BLAS threads per mode worker = cores // workers regardless of system size. With `workers=1`, small modal systems run on 4 BLAS threads. | `bor/solver.py:2832-2870` | Quiet host, 60-element sphere, 3 frequencies: `rhs_solve` + `rhs_compression` 0.18 + 0.48 s vs 0.01 + 0.02 s with one BLAS thread (30×). Whole run 11.7 s vs 11.0 s, so the absolute cost is small unless the host is contended. | Use 1 BLAS thread below ~1,500 unknowns | REPRODUCED (stage ratio) |
| S-9 | `rhs_compression='auto'` probes cost more than the solves they try to save: 7 of 38 factors probed, 0 productive, 2.9 s against 1.35 s of RHS solves. | `bor/solver.py:3101-3123` | PEC cone-cylinder, 12 GHz, 864 unknowns | ~16% of the mode phase (small against near preparation) | MEASURED |
| S-10 | Projection sample counts 32·p are not 5-smooth when the FFT path is chosen: 23 to 30 ns/sample at 1184, 1312, 1888 vs 12 to 14 at 1024, 2048. | `bor/kernels.py:511-553` | Micro-benchmark | Up to 2× on the projection for affected groups | MEASURED |
| S-11 | Default 1 GB tile budget may give tiles that run out of cache: 17.4 s CPU at 1.0 GB vs 14.7 s at 0.25 GB (one-row tiles at 0.06 GB are worse, 24.0 s). | `bor/streaming.py:876-918` | Single run, then interrupted | Possibly 10 to 15% of far build; needs re-measuring | MEASURED (one run) |
| S-12 | Default `mode_tol=1e-6` uses ~3 modes more than mesh accuracy warrants: 1e-3 differs from default by 1.2e-5 dB while the mesh error is 2e-2 dB. | `bor/dispatch.py:2066` | Cone-cylinder, 3 GHz | A few percent | MEASURED |

### Orchestration

| ID | Finding | Where | Evidence | Status |
|---|---|---|---|---|
| S-13 | Default result storage costs ~0.9 kB and ~13 µs per sample-polarisation. A 361×361 bistatic grid on a 68-panel body took 4.5 s and +221 MiB, of which the numerics were 0.33 s; under `compact_samples()` 1.1 s and +17 MiB. | `twod/solver.py:2235-2261, 3705-3724, 2973-3032` | MEASURED |
| S-14 | Under SLURM, every memory check reads `environ` and RSS of every PID on the host: 5.2 ms vs 0.036 ms per probe at 117 PIDs; linear in PID count. | `twod/solver.py:1359-1380` | MEASURED |
| S-15 | Sweep planning rebuilds candidate meshes per frequency, serially, before any worker starts: 8 frequencies took 2 s at N ≈ 1280 and 37 s at N ≈ 20k (loaded host). | `execution/frequency_sweep.py:144-175` | MEASURED (loaded) |
| S-16 | `frequency_workers='auto'` is capped at 2 workers with tile processes disabled inside them; likely leaves cores idle on hosts with more than 4 cores. | `execution/frequency_sweep.py:17, 34, 221` | INSPECTION |
| S-17 | Linux worker probe calls `memory_full_info` and uses only RSS: 1.25 CPU-s over 587 snapshots at N = 5120 (~2% of the solve). | `compressed/worker_pool.py:74-76` | MEASURED |
| S-18 | `execution/metrics.py:59` `sample_memory` walks the process table via psutil; 11.7 s cumulative over 4,108 calls in one contended BOR profile. | `execution/metrics.py:59` | MEASURED (loaded) |

---

## Memory findings

### M-1. Dense forecast omits the retained partner-polarisation matrix — REPRODUCED

- **Where:** `twod/solver.py:1621` (`solve = 2*matrix + ...`), `:1632` (hierarchical: `matrix + 0.65*matrix`); paired assembly at `twod/assembly/scatter.py:298-312`; LU copy at `linalg/dense.py:166`.
- **Evidence:** N = 5120 PEC, co-polarised dense solve. At the first `lu_factor`, tracemalloc shows 0.781 GiB (TE and TM systems) plus 0.391 GiB (LU copy): three N×N matrices, RSS 1.41 GiB. At the second LU only two are live (1.03 GiB).
- **Forecast vs measured peak (reviewer):** 0.443 vs 0.467 GiB at N = 2560; 1.112 vs 1.424 at 5120 (1.28×); 1.489 vs 1.962 at 6144 (1.32×).
- **Nuance:** the pairing itself is admitted at run time against the live limit (`twod/assembly/session.py:49-66`), so a single solve is protected. The exposure is in the planners that use the published forecast for concurrency (`execution/frequency_sweep.py:167` margin 1.25; `runs/local_twod_driver.py:100` and `hpc/twod_driver.py:149` margin 1.35), which the gap exceeds from about N = 5000.
- **Fix:** price `3*matrix` when paired assembly will be used, or release or spool the partner before the LU copy.

### M-2. Tile-compressed forecast over-predicts 2 to 2.6× — MEASURED

- **Where:** `compressed/tile_processes.py:19-23` (`WORKER_BYTES` = 480 MiB per worker), `compressed/worker_pool.py:204-216`, `compressed/memory.py:249-250`, `hpc/scheduler.py:742-770`, `execution/frequency_sweep.py:34, 144-175`.
- **Evidence:** forecast vs measured tree RSS: 0.415 vs 0.19 GiB at N = 1280; 2.899 vs 1.30 at 5120; 3.167 vs 1.62 at 6144. The H-matrix forecast is good (1.65 vs 1.35 GiB at N = 10240), so the forecast is non-monotonic across the 8192 threshold (3.72 GiB at 7936, 1.28 GiB at 8448).
- **Two specific mis-pricings:** the sweep planner prices tile workers that frequency workers never start (2.45 GiB planned vs 1.28 GiB as run); the batch planner prices the planning host's thread count rather than the unit's.
- **Consequence:** in the 4k to 8k band, planners admit 2 to 4× fewer concurrent solves than fit.

### M-3. Other memory items

| ID | Item | Where | Status |
|---|---|---|---|
| M-3a | BOR estimate has a ~2.8 GB floor: 2 to 6.5× above measured RSS for 234 to 1000 unknowns (e.g. 2.82 vs 0.43 GB, 3.73 vs 1.82 GB). Never under-predicted. Unknown and mode-cap counts were exact. | `bor/dispatch.py:1172-1175, 1417-1422`; `bor/solver.py:408-436` | MEASURED |
| M-3b | Dense HODLR peak exceeds LU's when the ordered copy is admitted: 1.28 N² extra vs 1.07 to 1.11 N² for LU at n = 6000; the forecast says 1.65 N² total against a real 2.2 to 2.3 N². | `linalg/hierarchical.py:195-231, 434, 53-56` | MEASURED |
| M-3c | Co-polarised dense solves peak at ~3.5 N² complex128 for PEC, IBC and coated bodies, 2.4 N² for a single dielectric (same cause as M-1). | `twod/formulations/regions.py:528-538` | MEASURED |
| M-3d | No leak across frequencies: RSS flat for LU and tile over 6 solves; HODLR rose 168 → 220 MB then plateaued. Threads, file descriptors and child processes constant. | — | MEASURED |

---

## Claims that did not reproduce

### N-1. "Default compressed profile is 5 to 11× slower than dense below ~8k unknowns"

Three reviewers reported this in different forms (default `factorization='compressed'` at `execution/options.py:540-554`; BLAS `auto` thresholds at `options.py:487-509`; HODLR and tile applies at `linalg/hierarchical.py:360-396`). Their figures included N = 300 at 7.1 s vs 0.64 s and N = 1280 at 18.2 s vs 3.1 s.

Re-measured by the lead on the same machine once the other reviewers had stopped (PEC circle, co-polarised, wall / CPU seconds):

| N | angles | default (compressed) | `solver_method='direct'` |
|---|---|---|---|
| 300 | 61 | 0.50 / 1.2 | 0.62 / 1.2 |
| 1280 | 61 | 3.4 / 7.8 | 3.5 / 5.1 |
| 2500 | 61 | 9.1 / 19.6 | 9.4 / 12.4 |
| 3000 | 181 | 12.5 / 29.0 | 13.4 / 17.8 |

Under contention the two stayed level: with 16 busy loops, 20.6 s vs 24.9 s at N = 1280; with 6 threaded-BLAS background processes, 29.9 s vs 36.6 s; four concurrent solves, 9.8 to 12.0 s vs 11.8 to 12.7 s.

**What survives:** the default path uses about 1.5× the CPU of dense for the same wall time, with no meaningful memory saving below the H-matrix threshold. The large ratios appeared only while five other audit processes were running BLAS-threaded work at load 15 to 30; the lead could not recreate them. S-8 is the one place a BLAS-thread stage ratio did reproduce, and there the absolute cost is under a second.

---

## Verified correct

These were checked numerically and are offered as a baseline for cross-examination.

**2D, complex amplitude vs analytic cylinder series (area-preserving polygon, TE and TM):**

| Case | ka | Panels | Max relative error |
|---|---|---|---|
| PEC, including interior resonances 1.841, 2.405, 3.832, 5.520 | 0.001 to 10 | 360 | 6e-11 to 9e-6 |
| IBC: 37, ±j100, 50-j200, 377, 1e-4 Ω | 0.05, 2.405, 5 | 360 | 2e-9 to 2.3e-4 |
| Dielectric: ε = 4; 4-0.2j; 12-1j; μ = 3; ε 2.5-0.04j with μ 1.3-0.02j | 0.01 to 5 | 360 | 1e-9 to 2e-5 |
| Dielectric annulus with air void | 0.5, 2.405, 5 | 480 | 2e-7 to 8e-5 |
| Coated PEC, coated IBC, two-layer dielectric, three-layer stacks | 0.05 to 5 | 720 | 1e-8 to 1.6e-4 |
| Closed TYPE 1 sheet shell, four impedances | 0.5, 2.405, 5 | 240 | 3e-7 to 6e-5 |

- Convergence order 3.0 for PEC, dielectric and coated PEC; 2.0 for IBC and resistive shell.
- Invariances to rounding on the dense path: co-polarised vs single-polarisation call (≤ 1e-14), rotation (≤ 5e-13), translation phase (≤ 8e-13), inches vs meters, multi- vs single-frequency (bitwise), bistatic diagonal vs monostatic (≤ 3e-15). Optical theorem 0.99999 to 1.00000 for lossless bodies.
- Backends agree with dense LU within about κ × 1e-12 on eight cases (2e-12 for PEC up to 9e-9 for a thin coat at κ = 1e5); PEC at N = 8192: HODLR 7e-15, H-matrix 2.7e-12 of peak.

**2D operator blocks vs independent quadrature (|k|L ≤ 3):** self S ≤ 4e-16; touching pairs from 1° to 170° with length ratios 0.05 to 20, S ≤ 1.4e-14 and K' ≤ 3e-13; adaptive near pairs with gaps down to 1e-3 h, S ≤ 6e-15 and K' ≤ 2e-13; assembled S, K', D, W on an irregular mesh with a thin gap ≤ 7e-13 and identical across NumPy, native and 1 or 3 threads (bitwise). ctypes signatures match the C prototypes; indices are 64-bit; no static mutable state in the 2D C code.

**BOR vs Mie (60 elements unless noted, 5 aspects × VV/HH):**

| Case | ka | Max error |
|---|---|---|
| PEC CFIE, including cavity resonances | 0.5 to 10 | ≤ 0.011 dB |
| PEC CFIE, 200 / 300 elements | 20 / 30 | 0.0008 / 0.0003 dB |
| IBC, six impedances | 1 to 6 | ≤ 0.04 dB |
| TYPE 1 sheet, five impedances | 1 to 4.49 | ≤ 0.05 dB |
| Dielectric, seven materials up to ε = 36-1j | 0.5 to 3 | ≤ 0.07 dB |
| Coated PEC, 2- and 3-layer | 1 to 5 | ≤ 0.08 dB |

- Convergence order 1.99 to 2.07. z-flip, z-translation phase, segment split (bitwise), units, frequency order (bitwise), `expand_to_360`, workers 1 vs 2 (1e-14 dB) all hold.
- BOR modal kernels vs an independent 3D reference: far ≤ 7e-14 for real k and ≤ 6e-12 for k = 60-300j, including near-axis radii of 1e-9; near rule 7e-15 to 6e-13 for d/ρ from 0.1 to 1e-7. Native and NumPy agree to 1e-16; 1 vs 4 OpenMP threads bitwise equal. The far tile budget is respected (0.94 to 1.08 of budget).

**Linear algebra:** HODLR inverse matches LU to 5e-16 with backward error 5 to 8e-16; condition estimators match exact values to 6 digits (dense) and 4 digits (H-matrix); residual spool round trip is bit-exact with no leaked files after abort or simulated disk-full; abort during assembly or factorisation propagates within 0.6 s and leaves no threads.

---

## Not covered

- Windows execution of any kind, including the shipped DLLs and commit-charge accounting.
- Problems above ~10k unknowns (2D) and ~1,000 unknowns (BOR); multi-GB forecast accuracy is untested.
- 2D: `twod/geometry.py` meshing and junction grading (exercised, not read line by line); partial coatings with TYPE 2+3+4 junctions against a reference; tapered impedances; the hp-adaptive (degree 2/3) certified path; mixed precision; `checkpoints.py`.
- BOR: banded and coating-patch layouts; `sharp_pairs.py`; `compressed_far.py`, `compressed_cross.py` and the spill/mmap machinery; `table_precision='single'`; `assembly='tables'`; the process-pool near backend; checkpoint resume.
- Compressed: the tile process-pool path (4096 < N < 8192), GMRES fallback and tightened-operator rebuild (never triggered), `fast_far.py`, block-Sinkhorn condition scaling.
- End-to-end runs of `run_local_*` and the HPC drivers.
