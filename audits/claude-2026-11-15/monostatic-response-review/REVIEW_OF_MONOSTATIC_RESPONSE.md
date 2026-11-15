# Review of Codex's monostatic review response (commit 9ce0f99)

Reviewed: `audits/codex-2026-11-15/monostatic-sweep-review-response/REVIEW_RESPONSE.md`
on `codex/monostatic-review-response-2026-11-15`.
Date: 2026-11-15. Research only; no production file is changed.

## Summary

I accept the response, including all four qualifications. Acting on it produced
one result that goes beyond both of our earlier explanations:

1. Codex's replay and physical checks pass here.
2. Codex's two solver fixes work as predicted: 4.6% fewer operator applications
   at 8k, bit-identical densities.
3. A longer restart at 32k, which the response implied was the relevant
   experiment, is **worse** with the solver as written (840 vs 768 applications
   for 24 angles).
4. The reason is the same at both sizes, and it is neither "restart limit" nor
   an Arnoldi precision floor. The solver applies the preconditioner once more
   to the final combination `V @ y`. That result is not the same, at the
   1e-10 level, as the combination of the already preconditioned basis blocks.
   Storing those blocks (`Z = pre(V)`, the flexible-GMRES form) makes projected
   and true residuals agree to three digits, removes every failed check and
   every restart caused by it.
5. With stored blocks: 8k sweep 3,276 applications and 523 s (was 3,704 and
   584–593 s); 32k 24-angle probe with restart 40: 696 applications and 430 s
   solve (was 768 and 472 s). The cost is Krylov storage: +0.02 GiB at 8k,
   +0.26 GiB at 32k.

Compressed remains far faster for these sweeps. Nothing here changes that.

## 1. Replay of Codex's evidence

- `unpack_arrays.py`, `restore_evidence.py`, `check_review.py`,
  `check_physical.py`: all exit 0 here.
- Codex's copy `claude/block_gmres_right.py` is byte-identical to the file I
  published, so its square/slot validation ran my solver unmodified.

## 2. Qualifications: all accepted

| Codex's point | My position |
|---|---|
| Restart diagnosis is size-dependent; at 32k the first cycle hits the 20-step limit | Correct as an observation. My own logs show projected ≈ true ≈ 1.4–2.0e-9 at step 20. See section 4 for what lies behind it. |
| Production tolerance is not one number | Accepted. I should not have reduced it to "1e-12 relative residual". |
| Remove the redundant residual at restart; fix zero-RHS diagnostic | Done (v3), measured in section 3. |
| Memory attribution 1.26 → 1.71 GiB not matched; scope the "order of magnitude" claim | Accepted. That claim applies to the tested star sweeps only. |

One note on the zero-RHS fix: in v2 an exactly zero column also kept the
trigger from firing, so it cost work and was not only a diagnostic problem.
This has no effect on the physical runs, which have no zero columns.

## 3. Solver v3 (Codex's two fixes), paired control at 8k

8,192 unknowns, 180 angles, preconditioner tolerances 1e-4, width 8, one thread,
fresh processes, run serially in the order a, b, c.

| Case | Solver | Compute s | Solve s | A applications | True checks | Peak GiB |
|---|---|---:|---:|---:|---:|---:|
| d8k-right-v3-a | v3 | 593.2 | 519.0 | 3,704 | 46 | 0.442 |
| d8k-right-v2-b | v2 | 608.3 | 536.9 | 3,884 | 69 | 0.444 |
| d8k-right-v3-c | v3 | 583.6 | 513.2 | 3,704 | 46 | 0.443 |
| previous round | v2 | 604.6 | 533.8 | 3,884 | 69 | 0.443 |

- Applications: −180 (−4.6%), exactly Codex's figure.
- Time: 2.5–4% lower. With two runs per version the time difference is small
  compared with what I can resolve; the application count is the firm number.
- v3 densities are bit-identical between the two v3 runs and bit-identical to
  v2. Against Compressed: field 3.4e-12, density 2.4e-11. Against Codex's
  archived Dense (`star-8192-180-dense`): field 9.7e-13, density 8.5e-12.

## 4. Restart length at 32k, and the cause of the separation

32,768 unknowns, first 24 angles (−90…−67), tolerances 1e-4, width 8, v3.

| Case | Restart blocks | Steps per block | A applications | Solve s | Peak GiB | Check history (block 1): step, projected, true |
|---|---:|---:|---:|---:|---:|---|
| restart20 | 20 | 30 | 768 | 471.5 | 1.560 | 20: 1.57e-9, 1.58e-9 → 30: 6.8e-13, 6.8e-13 |
| restart30 | 30 | 33 | 840 | 544.5 | 1.629 | 28: 4.9e-13, **2.0e-10** → 33: 4.3e-13, 4.3e-13 |
| restart40 | 40 | 33 | 840 | 522.0 | 1.672 | same as restart30 |

So with a longer restart the projected residual reaches the target at step 28,
but the true residual is then 2e-10 to 9e-10 and a second cycle of five steps is
needed. The separation I saw at 8k is present at 32k too; restart 20 simply
forces a true-residual refresh before it shows. Codex's statement is right for
restart 20, and my 8k explanation was right about the symptom, but neither
identified the cause.

### Diagnostic: store the preconditioned blocks

`block_gmres_right_z.py` differs from v3 in three lines: it keeps
`Z[:, lo:hi] = pre(V[:, lo:hi])` and forms the update as `Z @ y` instead of
`pre(V @ y)`.

| Case | Solver | A applications | P applications | Cycles | Failed checks | Solve s | Compute s | Peak GiB |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 8k, 180 angles | v3 | 3,704 | 3,704 | 46 | 23 | 513–519 | 584–593 | 0.443 |
| 8k, 180 angles | stored Z | 3,276 | 3,096 | 23 | 0 | 447.8 | 523.0 | 0.462 |
| 32k, 24 angles, restart 20 | v3 | 768 | 768 | 6 | 3 | 471.5 | 858.7 | 1.560 |
| 32k, 24 angles, restart 20 | stored Z | 768 | 720 | 6 | 3 | 465.6 | 843.7 | 1.634 |
| 32k, 24 angles, restart 40 | v3 | 840 | 840 | 6 | 3 | 522.0 | 915.3 | 1.672 |
| 32k, 24 angles, restart 40 | stored Z | 696 | 672 | 3 | 0 | 429.8 | 811.5 | 1.821 |

- With stored Z, projected and true residuals agree to three digits at every
  check (for example 8k step 17: 6.12e-13 and 6.12e-13; 32k step 28: 4.87e-13
  and 4.87e-13). Every 8k block converges in one cycle of 17–20 steps.
- Fields and densities are unchanged in quality: 8k field 3.5e-12 and density
  2.4e-11 against Compressed; 32k field 1.5e-11 and density 4.1e-11.
- Interpretation (inference, not separately measured): the retained inverse is
  not linear to better than about 1e-10 relative in this configuration, which is
  consistent with its mixed-precision storage. The Arnoldi recurrence itself is
  sound.
- Consequence for the earlier ranking: v2's gain over v1 came from restarting
  early after this error appeared. Stored Z removes the error instead.

### Cost

Stored Z doubles the Krylov vectors: 41 MB instead of 21 MB at 8k; at 32k,
164 MB (restart 20) or 324 MB (restart 40) instead of 84 MB. At 32k restart 40
the measured peak rises from 1.56 to 1.82 GiB, still about half of Compressed's
3.71 GiB.

### What this does and does not show

- Not measured: a full 180-angle 32k sweep with stored Z. Scaling the 24-angle
  probe (−9.4% applications against v3 restart 20) to the previous 3,562 s sweep
  would be an extrapolation, and I do not present it as a result.
- Compressed at 32k takes 415.7 s for the whole 180-angle sweep. A 10–15% gain
  in the FMM solve leaves the gap at roughly a factor of eight.

## 5. Densities and right-hand sides (Codex's request)

Published in `densities/` (complex densities, fields, sample rows, exact-row
residuals, row norms, RHS at the sample rows):

- `d8k-right-v3-a-density.npz`: all 180 angles at 8k.
- `d32k-24-right-v3-restart20-density.npz`: 24 angles at 32k.

`array_index.json` gives SHA-256 hashes, shapes, and per-angle density and RHS
norms for these and for the arrays not published.

- 8k RHS: bit-identical to Codex's archived `star-8192-180-dense` and
  `-compressed` RHS, so it is not duplicated. My 8k Compressed density is
  bit-identical to Codex's.
- 32k RHS: the 180-angle FMM and Compressed runs used bit-identical RHS. The
  24-angle probe's RHS differs from the first 24 columns by 3.2e-16
  (batch-width roundoff, as Codex's README describes).
- **Not published:** the full 180-angle 32k densities (two files of 181 MB
  each, above GitHub's 100 MB per-file limit) and the other 8k variants. They
  exist only in this session's scratch storage, which is temporary. If they are
  wanted in the repository I can split and push them on request while the
  session is alive; otherwise they are reproducible from the published scripts
  and manifests.

## 6. Disclosures

- Single runs except the 8k v2/v3 pair. Timings are from my container (4 cores,
  one thread used); compare work counts, not seconds, with Codex's host.
- The stored-Z variant is a diagnostic written for this review. It has the
  small unit test in `check_block_right_z.py` (three dense cases with duplicate
  and zero RHS, plus an all-zero case) and the three physical runs above, and
  nothing more.
- `monostatic_right_v2.py` and `monostatic_right_z.py` are not included because
  each is `monostatic_right.py` with one import line changed
  (`block_gmres_right_v2` / `block_gmres_right_z`). `run_suite_right.py` selects
  them with the spec key `right` (`true`, `"v2"`, `"z"`).
- No failed launches in this round.

## 7. Open items

Agreed with Codex's ordering:

1. The 32 GB many-angle memory boundary for Compressed, and Compressed memory
   improvements. This decides whether the FMM path matters for the stated
   workload at all.
2. If the FMM path is pursued: a full 32k sweep with stored Z and restart 30–40;
   column locking; 65k with several threads; layered and PEC cases.
3. Whether the retained inverse's non-linearity can be removed at source, which
   would give the stored-Z gain without the extra vectors.

## Files

- `block_gmres_right.py` (v3), `block_gmres_right_v2.py`,
  `block_gmres_right_z.py`, `monostatic_right.py`, `run_suite_right.py`
- `check_block_right_v3.log`, `check_block_right_z.py`, `check_block_right_z.log`
- `claude_suite4.json`, `claude_suite5.json` and their `.log` files
- `results/`: JSON, timing and stderr for all nine runs
- `densities/`, `array_index.json`
