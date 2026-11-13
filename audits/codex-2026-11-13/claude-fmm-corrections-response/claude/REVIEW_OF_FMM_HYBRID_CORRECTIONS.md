# Review of the FMM hybrid corrections

Reviewed: `origin/codex/fmm-hybrid-corrections-2026-11-13` at `98be27b` (research only). No production file
differs from `bfc5240`. I reran Codex's own scripts from that commit, unmodified, single-threaded, one fresh
process per case, on a 4-core 15 GiB host. Three small scripts of mine are added (`claude_*.py`).
Records are in `results/`.

Each statement below is marked **[run]** (measured here), **[read]** (code inspection) or **[estimate]**.

## Summary

1. **The straight-side repair is correct.** The square and stadium results reproduce to the printed digits,
   and the repair behaves properly on the awkward cases I probed. One small units caveat is noted.
2. **The reported far-field "accuracy limitation" is mostly an effect of the metric.** The stadium's absolute
   error is no larger than the square's. It only looks large because the stadium's biggest K entry is 44 times
   smaller. Measured against the system block K is added to, the error is 2.6e-13. I would not change the
   separation default for it.
3. **The 8,192-unknown comparison reproduces.** FMM with the loose inverse takes 1.6 times as long as existing
   Compressed and peaks 33% lower.
4. **New: the balance shifts with size.** At fixed panels per wavelength the FMM route goes from 2.3 times
   slower at 4,096 unknowns to 1.2 times slower at 16,384, while its memory saving grows from 19% to 45%.
   Iterations stay at 42–47.
5. **Not done:** the native control, coated and multilayer solves, the query-cache prototype and angle sweeps.

## 1. Straight-side repair

| Check | Result |
|---|---|
| Square, 1,400 panels, compression required **[run]** | S 2.1e-13, K 5.8e-13, K′ 5.8e-13, W 3.8e-13 (max-entry); identical to Codex |
| Stadium, 1,536 panels, separation 2 **[run]** | S 9.7e-14, K 1.26e-11, K′ 1.27e-11, W 2.3e-13; identical |
| Stadium, separation 3 **[run]** | S 7.7e-15, K 9.5e-13, K′ 9.5e-13, W 8.6e-15; identical |
| `check_safe_cross.py` **[run]** | Passes, including rejection of the subnormal case |
| Component zero on all 8 sampled rows, nonzero elsewhere **[run]** | Recovered to 1e-15 relative for sizes 1 down to 1e-15 of its partners |
| Same, size 1e-20 of its partners **[run]** | Dropped (rank 0, 100% of that component lost) |
| Component small everywhere, 1e-6 to 1e-20 **[run]** | Recovered to 1e-15 relative |

The one loss is the units caveat. A component that is zero on the sampled rows gets scale 1.0, so its
tolerance becomes an absolute 1e-13 in whatever units the matrix has. Anything below that is discarded.
That is harmless for the geometries tested, but it makes the result depend on length units. Using the largest
partner scale in place of 1.0 would remove the dependence. **[read]**

Production exposure: I agree with Codex's reading that production callers pass tolerances built from a nonzero
global norm, and Codex's direct test with a zero component passes here. **[run]** A fail-closed guard in
`cross_approximation` for non-finite or subnormal tolerances is still cheap insurance.

## 2. The far-field accuracy limit

I reproduced the stadium numbers, then asked how large the error is in absolute terms and relative to what K
is combined with in a solve (`claude_stadium_metric.py`, from the saved full matrices). **[run]**

| Case | Largest K entry | Largest K error (absolute) | Error ÷ largest K entry | Error of K + ikS ÷ its largest entry | Same, Frobenius |
|---|---|---|---|---|---|
| Square, sep. 2 | 8.7e-4 | 5.1e-16 | 5.8e-13 | 7.6e-13 | 6.7e-14 |
| Stadium, sep. 2 | 2.0e-5 | 2.5e-16 | 1.26e-11 | 2.6e-13 | 2.3e-14 |
| Stadium, sep. 3 | 2.0e-5 | 1.9e-17 | 9.5e-13 | 1.7e-14 | 4.4e-15 |

- The stadium's absolute error is half the square's. Its K matrix is simply small: 12% of entries are exactly
  zero and the largest is 44 times below the square's.
- The far field has an absolute roundoff floor of a few 1e-16 here, about 2e-13 of the ikS scale. That floor
  explains why asking for more digits does not help. Codex's digits 10/12/14 table is consistent with this;
  I did not rerun it.
- K never acts alone. In the transmission system it is added to the mass term and ikS, whose entries are 60
  times larger on this mesh. In that block the stadium is more accurate than the square.

So I read this as a property of the error metric on flat geometry, not a new defect. The suggestion is to state
the far-field error policy as an absolute error relative to the assembled block (or to k·S), not relative to
each operator's own largest entry. Separation 3 costs 43% more near pairs (452,928 against 316,676) **[run]**
and is not needed for this case. A reusable wideband translation is still worth studying for low-frequency
stability, but this stadium is not evidence that it is required.

Not done: digits 10/12/14 replacement, tree-depth transitions, graded supports, and the native
targeted-column control (no FMM2D build on this host).

## 3. Compressed preconditioning and ownership

- **Ownership [read + run].** `HMatrixSystem` touches `self.operator` only in construction (`build`,
  `compress_block`). `apply` uses the retained tree. Every run here reported the operator released and the
  forward, transpose and adjoint actions bit-identical after release. After detaching, a rebuild would fail on
  a `None` attribute. That is fail-closed but unhelpful; an explicit "detached" error would be clearer.
- **Relaxed gate [read].** The subclass accepts the loose operator when its sampled-row error is within ten
  times its tolerance, so a 1e-2 operator may be 10% wrong on sampled rows. That is acceptable only because
  the outer solve is checked independently, which it is.
- **Outer checks [read].** Acceptance is GMRES status, the FMM operator's own residual, and about 70 exact
  rows. The exact rows are the only check independent of the FMM operator. Production Compressed has the same
  kind of sampled gate, so this is comparable, but neither is a full-row certificate.
- **Gap to production acceptance.** No mesh or condition certification runs on the FMM path, the solve is two
  sequential GMRES runs with no shared Krylov information, and there is no memory admission or budget on FMM
  construction.

## 4. End-to-end comparison

Same mesh (star, ε = 3 − 0.08i, TE, two angles), serial, otherwise idle. "Wall" and "peak" are for the whole
process, measured from outside by `timed.py`, so they include validation and output. **[run]**

**8,192 unknowns, k = 80**

| Method | Setup s | Factor s | Solve s | Wall s | Whole-process peak GiB | Field vs Dense |
|---|---|---|---|---|---|---|
| Dense | 188 | 26 | 1.0 | 217 | 2.23 | — |
| Existing Compressed | 250 | 4.9 | 0.3 | 256 | 0.67 | 2.5e-13 |
| FMM + loose inverse, compressed near | 367 | 1.8 | 18.9 | 408 | 0.46 | 1.2e-14 |
| FMM + loose inverse, streamed near | 294 | 1.7 | 15.2 | 331 | 0.54 | 1.1e-14 |

Repeats of Compressed and FMM gave 256 s and 393 s with the same peaks. Iterations were 46/47, matching
Codex's 46/48 closely. Codex's table is confirmed, with one adjustment: Compressed's whole-process peak is
0.67 GiB, not 0.546. The script's own figure is taken at the solve (0.57 here), before the far-field and
output stage. On the whole-process figure the FMM saving is 33%, not 20%.

The streamed-near variant is a useful middle point: 29% slower than Compressed for 19% less memory.

**Fixed panels per wavelength (about 42), k and panels doubling together**

| Unknowns, k | Compressed wall s / peak GiB | FMM wall s / peak GiB | FMM time ratio | FMM memory saving | Iterations | Field difference |
|---|---|---|---|---|---|---|
| 4,096, 40 | 93 / 0.36 | 211 / 0.30 | 2.26 | 19% | 42/42 | 2.7e-13 |
| 8,192, 80 | 256 / 0.67 | 408 / 0.46 | 1.59 | 33% | 46/47 | 2.5e-13 and 1.2e-14 vs Dense |
| 16,384, 160 | 671 / 1.37 | 823 / 0.76 | 1.23 | 45% | 44/46 | 3.0e-13 |

- Compressed's time grows 2.6–2.8 times per doubling; the FMM route's grows about 2.0 times.
- The loose inverse grows 25 → 62 → 165 MiB, about 2.6 times per doubling. It is the part of the FMM route
  that does not scale linearly.
- If both trends held, the two would cross in time somewhere near 30,000–60,000 unknowns. **[estimate]**
  That is an extrapolation from three points on one shape.
- The field differences at 4,096 and 16,384 are between FMM and Compressed, with no Dense run. They match
  Compressed's own difference from Dense at 8,192, so they probably reflect Compressed's accuracy.

Where the FMM time goes at 16,384 unknowns: 339 s building the loose operator for the preconditioner, 408 s
building the two FMM operators, 36 s solving. Near-field kernel evaluation is done twice, once for each. That
duplication is the clearest target.

## 5. Not done

- Thin coated PEC body, multilayer dielectric, high contrast, resonant shapes, severe grading (task 5).
  The research operator handles one homogeneous dielectric only; these need a multi-region formulation first.
- Bounded near-query cache, panel-block compression with nodal folding, 1/16/181-angle workflows, H²/HSS
  comparison (task 6).
- Sharing source and target moments for real k: the target table is the complex conjugate of the source table
  when k is real, which would cut the exterior far tables by 40%. **[read]** Not measured.

## 6. Recommendations

1. Accept the straight-side repair for the research prototype. Replace the fixed scale 1.0 for unseen
   components with the largest partner scale.
2. Do not adopt separation 3 or treat the stadium as a blocker. Restate the far-field error policy relative to
   the assembled block.
3. Keep Dense and Compressed as they are. The FMM route is not yet faster at any size measured.
4. The scaling trend justifies one more bounded step: 32,768 and 65,536 unknowns at the same sampling, to see
   whether the time crossover is real and whether inverse memory keeps growing at 2.6 times per doubling.
5. Before that, remove the duplicated near-field work by building the preconditioner from the same near
   evaluations as the FMM operator. On these figures that is up to 40% of the FMM route's time.
6. Physical qualification (coatings, multilayer, both polarisations) remains the largest untested area and
   needs a multi-region research operator.

## Files

- `claude_safe_cross_probe.py` → `results/claude_safe_cross_probe.json`
- `claude_stadium_metric.py` → `results/claude_stadium_metric.json`
- `run_e2e.sh`, `run_e2e_repeat.sh`, `timed.py`, `claude_e2e_table.py` → `results/e2e-*`, `results/ppw-*`,
  `results/e2e_table.txt`
- `results/matrix-*.json` are reruns of Codex's `combined_benchmark.py` cases (full matrices not retained).

To rerun: copy the scripts into Codex's `audits/codex-2026-11-13/fmm-hybrid-corrections/`, set `GRIM_ROOT`
to the checkout root, and run them there.

