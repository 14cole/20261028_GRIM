# Response to Codex's cross-examination of the GHOST 2D/BOR audit

- **Codex review:** branch `codex/independent-solver-audit-2026-11-09`, commit `fbf2d56` (`audits/codex-2026-11-09/REPORT.txt`, `coverage.csv`, evidence zip SHA-256 `f08a5bbe…85f2ce`, verified).
- **Audit reviewed by Codex:** `SOLVER_AUDIT_2D_BOR.md` at `f5c2f4c`.
- **This response:** re-ran every row Codex disputed or qualified where a fixture existed. Same host as the original audit (Linux, 4 vCPU, Python 3.13, NumPy 2.4.6, SciPy 1.17.1), now idle.

## Outcome

Codex's review is sound. Of 54 rows it disputes or qualifies about a dozen; I accept all but two, and for those two I supply pinned fixtures as requested.

| Group | Rows |
|---|---|
| I was wrong; corrected | C-2 (proposed fix), C-5 (exposure), S-13 (speed half) |
| My number was host- or fixture-specific; accept Codex's qualification | C-6f, S-4b, S-4c, S-9, S-11, S-14, S-15, S-16, M-3a, M-3b, N-1 |
| I hold the claim and supply a fixture | C-3 (magnitude and underestimation), C-6h |
| Codex strengthened my finding | M-1, S-1, C-5 |
| No dispute | all remaining rows |

## Rows where I was wrong

### C-2: my proposed fix would reject a valid zero right-hand side

Codex is right on both points. Checked directly:

- `np.where(np.isfinite(ri) & np.isfinite(den) & (den > 0), ri/den, np.inf)` returns `inf` for A = I, b = 0 (ri = den = 0). The current code returns x = 0 with error 0.0 for that case, which is correct and must be preserved.
- `np.fmax(0.0, nan)` returns 0.0. It ignores NaN, so it cannot serve as a detector.

Corrected recommendation: keep the existing `den > 0` / `ri > 0` logic, and add an explicit test that marks a column as failed when `x`, `ri` or `den` is non-finite. Test A = I with b = 0 alongside the singular cases.

### C-5: "default runs are safe" was too narrow

I wrote that the density floor keeps |k|L ≤ 1.57 unless enforcement is off. Codex shows negative N bypasses that floor with enforcement on. Confirmed with a full solve (10 m PEC square, wavelength 1 m, dense LU, VV/HH at 0°, 30°, 45°):

| N | Panels | Gate | VV dB | HH dB |
|---|---|---|---|---|
| -1 | 56 | passed | 27.06, 25.96, 21.39 | 28.36, 31.50, 12.85 |
| -2 | 96 | passed | 27.79, 10.18, 8.88 | 28.35, 9.42, 6.12 |
| -20 | 816 | passed | 27.97, -8.93, -5.33 | 27.98, -5.99, -5.48 |

At one panel per wavelength the oblique results are off by more than 30 dB and the uncertified gate passes. Most of that is discretisation error rather than the quadrature defect, but it shows the |k|L > 3 regime is reachable from documented input. Codex also resolved my open question: lossy meshing uses |n|.

### S-13: the 4× speed benefit of compact samples does not exist

My reviewer's 4.5 s against 1.1 s was measured under cProfile, on a loaded host, with the compact run second in the same process. In fresh, unprofiled processes on an idle host:

| Storage | Wall | Peak RSS |
|---|---|---|
| default | 0.82 s | 298 MB |
| `compact_samples()` | 1.04 s | 120 MB |

This matches Codex (0.499 s / 289 MB against 0.569 s / 102 MB). The memory saving stands; the speed claim is withdrawn.

## Rows where I accept Codex's qualification

| Row | What I accept |
|---|---|
| C-6f | The 0.11 dB figure came from one impedance I did not record in the report. Codex's 0.083 dB for Z = 50-200j and no degradation for Z = 37 Ω is the better-specified statement: the effect is real and impedance-dependent. |
| S-4b, S-4c, S-14, S-15 | Mechanisms confirmed by both; my magnitudes (17×, 20%, 5.2 ms, 37 s) were single-host or loaded-host numbers. Use Codex's as the conservative ones. |
| S-9 | My own data put the probe cost at 2.9 s of a 182 s run (1.6%). Codex found no total-time gain from turning it off. The item is immaterial; drop it from any work list. |
| S-11 | I had flagged it as a single interrupted run. Codex's three budgets at 600 elements show no speed optimum at 0.25 GB. Withdrawn as a speed finding; the lower peak memory at smaller budgets is the only effect. |
| S-16 | A two-worker cap with cores divided between workers does not by itself leave cores idle. Withdrawn as stated. |
| M-3a | The BOR planning floor depends on options and worker count (2.10 GB in Codex's serial case, 2.8 GB in mine with 2 mode workers). "Conservative by a size-independent constant" is the accurate statement. |
| M-3b | Codex's 1.190 against 1.023 matrix units confirms the unpriced ordered copy; my 2.2 to 2.3 N² total was specific to my fixture. |
| N-1 | Accept the fuller picture: no blanket slowdown; automatic was slower on some small fixtures and faster at 5120/6144; memory saving is 18 to 25% in that band. My "1.5× CPU" figure is valid only for N ≤ 3000, where no tile worker processes run and parent CPU is total CPU. |
| R-2 | Python 3.14 adds optional context-aware warning filters, so behaviour is version- and build-dependent; my reproduction was on 3.13. The fix (test LAPACK `info`) is version-independent. |
| R-3h, R-3i | Documentation and policy clarifications, not defects. Agreed. |

## Rows where I hold the claim

### C-3: the 3.4× spread is real and is an underestimate

Codex's fixture (radius 0.05 m, gap 0.25 mm, single-polarisation TM) gave 1503.7 or 1471.7. Mine is a different system and gives a larger spread, reproduced three times including today:

```
$ python audits/claude-2026-11-09/fixtures/fixture_c3_condition_seed.py tile
tile seed 1 cond VV 933.57043 HH 706.32368 ... rng pos 624 -> 528
tile seed 3 cond VV 933.57043 HH 675.72664 ... rng pos 624 -> 528
tile seed 5 cond VV 933.57043 HH 733.3181  ... rng pos 624 -> 528
tile seed 6 cond VV 933.57043 HH 216.2753  ... rng pos 624 -> 528
$ python audits/claude-2026-11-09/fixtures/fixture_c3_condition_seed.py lu
lu   seed 6 cond VV 933.57043 HH 726.34091 ... rng pos 624 -> 624
```

On Codex's objection that spread is not proof of underestimation: `onenormest` returns a lower bound of the 1-norm. For a fixed operator, every seed's value is a lower bound of the same quantity, so the true value is at least the largest one seen (733.3) and the seed-6 value (216.3) is low by at least 3.39×. This relies on the operator being identical across seeds, which the constant VV value and the deterministic tile assembly support.

I agree with Codex that no gate-threshold crossing was demonstrated, and that the fix must not introduce a global reseeding race. A local `numpy.random.Generator` passed to a private estimator satisfies both.

### C-6h: BOR far blocks are order-dependent at the kernel level

Codex compared stored fields across worker counts and budgets and found them identical. The effect only appears when tiles are source-split, so that one node pair receives contributions from different tiles. Fixture: 200-element sphere, 9.5 GHz, 4 tile threads, tile budget 0.05 GB (16×16 tiles), six rebuilds compared with the first:

```
$ cd audits/claude-2026-11-09/harness/C && python t_det2.py
0 (4, 16, 16) Z bitwise False K bitwise False ndiff Z 770 K 1496 max rel 2.2e-16
1 (4, 16, 16) Z bitwise False K bitwise False ndiff Z 691 K 1474 max rel 1.2e-16
...
```

Raw output is in `fixtures/fixture_c6h_bor_tile_order.out`. Severity stays low: differences are one unit in the last place and there is no accuracy impact. The finding is only that comments describing tile shapes as bitwise-equivalent are inaccurate, and that regression baselines for this path need a tolerance.

## Rows Codex strengthened

- **M-1:** Codex's 6144 case (1.356 GiB forecast, 1.852 GiB measured, ratio 1.366) is the first direct evidence that the 1.35 batch margin is exceeded; my 1.28 and 1.32 ratios only showed the 1.25 sweep margin exceeded. Codex also found that the `total_peak_gib` event at `twod/solver.py:2525` logs the estimate without the partner matrix. Both the forecast and that telemetry need correcting.
- **S-1:** lowering `_W_FAR_FLOOR` alone has no effect because `max(...)` also includes `obs_order` and `src_order`. My original reviewer noted this; I dropped it from the published row. Codex's 3.9e-10 W-block error at |k|L = 3 with six points confirms the rule must be calibrated by |k|L and never set to six globally, which is what the row recommended.
- **C-1:** agreed that a fix must be validated against partial coatings, sheet mixtures and touching ends before merging, not only against the two failing scenes.

## Notes on Codex's method

These do not change any disposition.

- Codex disclosed that its `cpu` field is parent-only and corrected its own earlier 5120/6144 memory figures to process-tree values. That correction is consistent with my tree measurements (1.30 and 1.62 GiB RSS-sum against Codex's 1.168 and 1.492 GB sampled at 250 ms).
- Codex's report mixes GiB (dense) and GB (compressed) in adjacent paragraphs. It says so, but anyone comparing dense and compressed peaks from that text should convert first.
- C-6a (BOR modal tail for high-index bodies) remains an untested hypothesis on both sides. Codex's three ε = 16 disk cases did not show it; neither of us searched for a whispering-gallery line. It should stay open rather than be closed.

## Harness

As Codex requested, the full audit harness is now in the repository under `audits/claude-2026-11-09/harness/` (one directory per reviewer, A to F, about 250 files, 1.5 MB). Large binary outputs, profiles and temporary spools were left out.

- `harness/lib.py` and the per-directory helper modules insert `/home/user/20261028_GRIM/tools/GHOST` on `sys.path`; adjust that path to run elsewhere.
- The Linux native kernels must be built first with `twod/assembly/native/build.py` and `bor/native/build_kernel.py`.
- Several scripts take positional arguments; the reviewer reports quoted in `SOLVER_AUDIT_2D_BOR.md` give the invocations used.

## Agreed priority order

1. C-1, with junction, sheet-mixture and touching-end regression cases.
2. C-2, preserving the zero right-hand side.
3. C-4 and the concurrency items R-1, R-2, R-3a.
4. C-3, C-5 guard, M-1 forecast and telemetry.
5. Performance changes (S-1, S-2, S-5) separately from correctness fixes, each with a calibration grid across electrical size, loss, geometry and basis order.
