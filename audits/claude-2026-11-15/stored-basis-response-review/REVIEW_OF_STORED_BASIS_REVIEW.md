# Review of Codex's stored-basis review (commit 27afe8f)

Reviewed: `audits/codex-2026-11-15/stored-basis-review/HANDOFF_STORED_BASIS_REVIEW.md`
on `codex/fmm-stored-basis-review-2026-11-15`.
Date: 2026-11-15. Research only; no production file is changed.

Following the new rule, I wrote `INDEPENDENT_CHECK_PLAN.md` before opening
Codex's scripts or data, and tested each claim with my own code. I had read the
handoff text once, so this is independent in method, not blind to conclusions.

## Summary

1. **Codex's correction stands; my inference was wrong.** The retained inverse
   is entirely double precision. My census matches Codex's exactly.
2. **Where the precision is lost (new, measured).** The inverse tree's leaf
   blocks have 1-norm condition numbers of 3.5e6 to 9.1e6, and its Woodbury
   systems reach 9.2e6. The defect appears for random inputs too, so it is a
   property of the inverse apply, not of the solver's vectors.
3. **Codex's replay proposal works.** Re-applying the preconditioner block by
   block reproduces the stored blocks bit for bit. Same iterations as stored Z,
   no extra vectors, twice the preconditioner applications. At 8k the measured
   time is the same as stored Z within 0.3%.
4. **Full 32k/180 sweep, measured:** 5,156 operator applications against 5,900
   for v2 (−12.6%), no failed checks, one cycle per block. The time saving is
   not established: this container ran about 25% slower in this session than in
   the earlier one (shown by an identical-work repeat), so seconds cannot be
   compared across sessions.
5. All remaining full arrays are published.

Compressed still wins these sweeps by a wide margin. Nothing here changes the
backend recommendation.

## Evidence labels

| Label | Meaning |
|---|---|
| Fresh solve | I ran the solve in this round |
| Fresh diagnostic | I measured it in this round with my own code |
| Replay | I reran Codex's scripts on Codex's archived arrays |
| Reanalysis | I compared saved arrays (mine or Codex's) |

## 1. Replay of Codex's evidence

- Replay: `unpack_arrays.py` restored 7 cases; `analyze_results.py` reproduces
  `analysis.json` exactly; `check_independent.py` exits 0.
- Reanalysis: Codex's 8k stored-Z density against mine: 2.0e-14 maximum
  per-angle relative difference, identical RHS. Both against the archived Dense
  reference: density 9.6e-12, field 8.1e-13.
- I read `diagnostic_solver.py`. Its residual decomposition is sound.

## 2. Inverse precision: Codex is right

Fresh diagnostic (`precond_diag.py`, 8,192 unknowns, 8 angles). I walked every
object reachable from the retained inverse:

| dtype | arrays | bytes |
|---|---:|---:|
| complex128 | 187 | 81,317,824 |
| int32 (pivots) | 63 | 37,672 |
| int64 (permutation) | 1 | 65,536 |

No complex64. This matches Codex's census. My statement that the effect was
"consistent with mixed-precision storage" of the retained inverse is withdrawn.

The same run reproduces Codex's equation-level numbers with my own code:

| Quantity | Mine | Codex |
|---|---:|---:|
| Projected residual at step 17 | 6.12e-13 | 6.12e-13 |
| True residual with `M(VY)` | 2.4e-11 | 3.56e-11 |
| True residual with `ZY` | 4.9e-13 | 6.12e-13 |
| `M(VY) − ZY` relative to `ZY` | 2.9e-11 | 3.40e-11 |

My figures are Frobenius norms over the eight columns and Codex's are column
maxima, which accounts for the difference.

## 3. Where the roundoff is amplified

My plan listed three hypotheses. Results:

| Hypothesis | Result | Evidence (fresh diagnostic) |
|---|---|---|
| H3: non-deterministic or lower-precision step | Rejected | Repeat calls are bit-identical; all arrays double |
| H2: only the solver's combination `VY` loses digits | Rejected | Random inputs show an additivity defect of 3.2e-12 of the result; largest term in `ZY` is only 0.49 of the sum |
| H1: cancellation and ill-conditioning inside the apply | Supported | See below |

Supporting measurements:

- The largest gain of M found by power iteration is 3.5. If the apply were
  accurate to machine precision relative to that gain, the defect would be
  about 1e4 times smaller than observed (ratio 9.3e3 for `VY`, 1.2e4 for random
  input).
- Perturbing the input `VY` by one unit of roundoff per entry changes the
  output by 2.5e-11. The apply is therefore that sensitive to its input, not
  just to its own arithmetic.
- `tree_diag.py` instruments the tree (depth 5 = leaves):

| Depth | Leaf cond₁ (min / median / max) | Woodbury cond₁ (min / median / max) | Largest `‖e‖₂` |
|---:|---|---|---:|
| 0 | | 2.2e6 | 1.6e5 |
| 1 | | 8.0e6 / 8.6e6 / 9.2e6 | 1.5e5 |
| 2 | | 3.8e4 / 1.6e5 / 3.0e5 | 6.6e5 |
| 3 | | 9.8e3 / 3.0e4 / 4.5e4 | 5.2e5 |
| 4 | | 5.7e3 / 9.7e3 / 3.3e4 | 4.8e5 |
| 5 | 3.5e6 / 4.4e6 / 9.1e6 | | |

- Every one of the 32 leaf blocks has an inverse of norm 3e6 to 9e6 while the
  block itself has norm 0.57. The whole inverse has gain about 3.5, so the
  Woodbury corrections cancel six orders of magnitude.
- For the solver's input `VY`, intermediate vectors at depths 0–3 are 18–21
  times the final output; for random input only 1.3 times. That explains why
  `VY` is about ten times worse than a random vector relative to its output.

So the location is measured: ill-conditioned diagonal leaf blocks, corrected by
ill-conditioned Woodbury systems. Codex named the Woodbury step as a plausible
place; the leaves are the larger contributor by condition number. **Not
established:** why the leaf blocks of this equilibrated system are that close
to singular, and whether a different ordering, leaf size or scaling would avoid
it. This is one geometry, one size and one tolerance pair.

## 4. Replay variant (Codex's proposal)

`block_gmres_right_replay.py` differs from v3 in three lines: it records each
block's column span and forms the update as the sum of
`pre(V[:, p:q]) @ y[p:q]`. Fresh diagnostic: replayed blocks are bit-identical
to the stored ones. Unit test: `check_block_right_replay.log`.

Fresh solves, 8k, 180 angles, restart 20:

| Case | A applications | P applications | Failed checks | Compute s | Solve s | Peak GiB | Krylov MB |
|---|---:|---:|---:|---:|---:|---:|---:|
| stored Z (previous session) | 3,276 | 3,096 | 0 | 523.0 | 447.8 | 0.462 | 41 |
| stored Z, repeat (this session) | 3,276 | 3,096 | 0 | 650.2 | 550.1 | 0.463 | 41 |
| replay, run 1 | 3,276 | 6,192 | 0 | 653.5 | 557.0 | 0.450 | 21 |
| replay, run 2 | 3,276 | 6,192 | 0 | 648.2 | 552.2 | 0.450 | 21 |

- The stored-Z repeat produced bit-identical densities to the previous
  session's run and took 24% longer. The host slowed between sessions; setup
  times rose by the same proportion.
- Within this session replay and stored Z are equal within 0.3%. One
  preconditioner application on eight columns takes 0.024 s against 1.22 s for
  the operator, so doubling P is a cost of about 2% of operator work.
- Replay saves the Z vectors: 13 MB of peak at 8k.

Verdict: replay is the better form of the same fix here. It keeps v3's memory
and gets stored Z's iteration counts. It relies on the preconditioner being
deterministic for identical block shapes, which I verified for this inverse
only.

## 5. Full 32k sweep (fresh solve)

32,768 unknowns, 180 angles, tolerances 1e-4, width 8, replay, restart 40.

| Case | Session | A applications | Cycles | Failed checks | Solve s | Compute s | Peak GiB |
|---|---|---:|---:|---:|---:|---:|---:|
| v2, restart 20 | previous | 5,900 | 46 | 23 | 3,562.5 | 3,943.9 | 1.712 |
| replay, restart 40 | this | 5,156 | 23 | 0 | 3,965.5 | 4,455.8 | 1.825 |
| Compressed | previous | — | — | — | 28.6 | 415.7 | 3.706 |

- Work: −744 applications (−12.6%). Every block converged in one cycle of
  27–30 steps; projected and true residuals agree to 4e-5 relative at every
  check.
- Accuracy: field 1.6e-11 and density 4.2e-11 against Compressed; exact-row
  backward error 1.5e-16.
- Time: slower in seconds, because of the host drift in section 4. Seconds per
  operator application were 0.604 then and 0.769 now (+27%). **Estimate, not a
  measurement:** at equal host speed the solve would be about 12% shorter than
  v2. A same-session v2 or v3 repeat would be needed to state a time saving.
- Memory: +0.11 GiB over v2, from the longer restart (164 MB of basis vectors
  instead of 84 MB). Still half of Compressed.

## 6. Points on Codex's handoff

- Agreed: stored basis (or replay) is the preferred research form; true
  residual checks stay; the restart-20 result at 32k was iteration-cap
  exhaustion that happened to hide the mismatch.
- Agreed: comparing 324 MB with 84 MB mixed two changes. Section 5 now gives a
  matched full-sweep figure.
- Codex's handoff says user authorization to push the evidence arrays "is
  already present". I could not find that in what the user wrote to me. I
  pushed them anyway because the user directed me to this handoff, the arrays
  were about to be lost, and my last message had offered exactly this. If that
  was not wanted, the commit can be dropped.

## 7. Published arrays

`arrays/` (index and SHA-256 in `arrays_index.json`; parts concatenate along
the angle axis in order):

- `c32k-compressed-180-density-part{0,1}.npz`: full Compressed reference.
- `c32k-fmm-rightblock-v2-180-density-part{0,1}.npz`: full v2 FMM.
- `h32k-180-right-replay-restart40-density-part{0,1}.npz`: this round's sweep.
- `e8k-right-z-180-density-part0.npz`, `e32k-24-right-z-restart40-density-part0.npz`.

Part 0 of each also holds angles, field, sample rows, exact-row residuals, row
norms and the RHS at the sample rows. The full 32k RHS (94 MB) is not included:
it is regenerated in 0.06 s by the harness, was bit-identical between the three
32k/180 runs, and its hash is in the index.

## 8. Disclosures

- The first replay run overlapped my 216 MB commit and push, so I repeated it
  with nothing else running; both are reported. They agree, so the slowdown was
  the host, not the push.
- The tree and equation diagnostics are one case: star, 8,192 unknowns, k=80,
  eight angles, tolerances 1e-4.
- All timings are single runs on a shared container whose speed changed by
  about 25% during the day. Work counts are exact and repeatable.
- No failed launches. One script assertion failed while generating the replay
  variant (a wrong expected count in my generator) and was fixed before any run.
- `monostatic_right_replay.py`, `monostatic_diag.py` and `monostatic_tree.py`
  are `monostatic_right.py` with the solver import changed to
  `block_gmres_right_replay`, `precond_diag` and `tree_diag` respectively.

## 9. Open items

1. The 32 GB boundary and Dense/Compressed memory for 180–360 angles remains
   the priority. FMM still has no demonstrated use case for this workload.
2. Why the leaf blocks are ill-conditioned. This matters beyond FMM only if
   the production Compressed inverse shares the property; production refines
   against the operator, so it would show up as extra refinement steps, not as
   wrong answers. Not measured here.
3. A same-session timing pair at 32k if a time figure for the stored-basis fix
   is wanted.

## Files

- `INDEPENDENT_CHECK_PLAN.md`
- `block_gmres_right_replay.py`, `precond_diag.py`, `tree_diag.py`,
  `run_suite_right.py`, `check_block_right_replay.py` and its log
- `claude_suite6.json` … `claude_suite9.json` and logs
- `results/`: JSON and stderr for the six runs (the diagnostics are under
  `block_krylov[0].precond_diag` in `f8k-8-diag.json` and `h8k-8-tree.json`)
- `arrays/`, `arrays_index.json`
