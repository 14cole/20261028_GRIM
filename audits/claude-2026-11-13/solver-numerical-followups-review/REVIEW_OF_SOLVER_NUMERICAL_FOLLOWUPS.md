# Review of Codex's solver numerical follow-ups

- **Reviewed code:** `codex/solver-numerical-followups-2026-11-12` at `ee66611` (production baseline `965d941`; seven runtime files and one document, 201 lines added, 32 removed).
- **Reviewed document:** `audits/codex-2026-11-12/solver-numerical-followups/HANDOFF_SOLVER_NUMERICAL_FOLLOWUPS.md`.
- **Host:** Linux, 4 vCPU, 15 GiB, Python 3.13. No Windows.

## Verdict

Accept `ee66611`. All three numerical items from my last review are addressed and measured as fixed on my host, every correctness check passed, and I found no defect by reading or by test. Two consequences need to be understood before release: Dense, the reference backend, now gives slightly different answers (up to 8.7e-10 on an ordinary coated model), and Dense is 13 to 17% slower on dielectric and coated bodies because of extra refinement passes (F1).

## What I checked

| Check | Result |
|---|---|
| Runtime diff read in full | No defect found |
| Line endings, native binaries | Preserved, unchanged |
| Regression suite, 11 scripts | 207 passed, 0 failed |
| Codex `test_numerical_followups.py` | 9 of 9 |
| My admission test; concurrency test, three runs | 9 of 9; 3 of 3 |
| Reference fields against `49bd93f` | 14 of 31 sets bitwise equal; 17 changed by at most 5.6e-12 (expected, see section 1) |
| 72 solves of my own, alternating old and new trees | Below (`nf.jsonl`, full fields in `fields/`) |

## 1. Dense LU is now equilibrated

**Transformations.** With the factor taken of the row- and column-scaled matrix, a normal solve divides the right-hand side by the row scales and the result by the column scales; transpose and conjugate-transpose solves swap the two. I checked this algebra against the code and it is right. The condition estimator calls the same routine, so it still estimates the same quantity. Every use of the Dense LU factors in the 2D path goes through the new routine; none applies the raw factors. Body-of-revolution solves do not use this class and are unchanged.

**Order on the disk path.** The original matrix is written to the spool first, then the buffer is scaled in place and factored, and the paired-polarization restore reads the original back from disk. Original coefficients are preserved before anything overwrites them. Disk and in-memory Dense gave bitwise-identical fields on the dielectric, coated and airfoil cases and 5e-15 on the PEC case.

**Effect at extreme scale** (same electrical problem, drift from the 100 m solution after amplitude scaling):

| Body | Radius | Dense drift before | Dense drift after |
|---|---|---|---|
| Coated PEC | 1 m | 6.5e-11 | 3.8e-12 |
| Coated PEC | 0.01 m | 1.2e-8 | 3.5e-12 |
| Dielectric | 1 m | 7.3e-12 | 5.4e-14 |
| Dielectric | 0.01 m | 8.1e-12 | 6.3e-14 |

**Effect on ordinary models.** Dense results move, and Compressed now agrees with Dense more closely than before, which indicates the old Dense was the less accurate of the two in these comparisons:

| Case | Unknowns | New Dense vs old Dense | Compressed vs Dense, before | Compressed vs Dense, after |
|---|---|---|---|---|
| PEC circle | 8,000 | 5.2e-15 | 3.2e-12 | 3.2e-12 |
| Dielectric circle | 8,000 | 2.7e-11 | 2.7e-11 | 3.7e-12 |
| Coated circle | 6,480 | 8.7e-10 | 9.2e-10 | 5.6e-10 |
| Airfoil 3 GHz | 8,666 | 1.7e-10 | 1.8e-10 | 6.9e-12 |

Repeated new Dense runs are bitwise identical to each other.

## 2. Legacy tile path

Dielectric circle below the hierarchical threshold (800 unknowns), Compressed against Dense:

| Radius | Before | After |
|---|---|---|
| 100 m | 2.3e-13 | 5.3e-15 |
| 0.01 m | 3.6e-8 | 6.0e-15 |

Fixed for this case. I did not run thin layers; Codex's thin-layer scan and its derivation of those multipliers rest on its own tests. Codex reports the fix costs storage on the tile path (10 to 25% in its cases) because some tiles are now kept exact; I did not measure that.

## 3. Compressed on single-dielectric bodies

Dielectric circle, 8,000 unknowns, three alternating pairs: 36.3, 36.8, 34.9 s before; 32.1, 32.2, 32.9 s after. About 11% faster, with bitwise-identical fields. At 12,000 unknowns, one pair: 58.2 s to 51.9 s. PEC, coated and airfoil Compressed runs are unchanged in time and bitwise identical in result.

Codex is right that my earlier "condition estimate is 40% of the run" figure was inflated: that stage was being timed twice. The slowdown itself was real, and its cause was an inverse rebuild, not the probes. I accept the correction.

Net position against the tree before the scale fix: this case took about 31 s then, 44 s after the scale fix, and 32 s now, with agreement to Dense improved from 1.3e-8 to 3.7e-12.

## Findings

### F1 (low to medium): Dense is 13 to 17% slower on dielectric and coated bodies

Two alternating pairs each, wall seconds:

| Case | Before | After | Inverse applications |
|---|---|---|---|
| PEC circle, 8,000 | 28.0, 27.7 | 28.4, 28.5 | 4 → 4 |
| Dielectric circle, 8,000 | 20.9, 21.3 | 24.8, 24.7 | 2 → 4 |
| Coated circle, 6,480 | 15.4, 15.2 | 17.0, 17.6 | 2 → 4 |
| Airfoil 3 GHz | 24.4, 24.9 | 26.6, 25.6 | 2 → 2 |

With disk residuals the pattern is the same (dielectric 23.7 → 27.5 s, coated 21.7 → 23.9 s). Peak memory is unchanged within 3%.

The cause is the refinement loop: it now continues until the scaled error reaches 3e-15, not merely until the 1e-12 release gates pass, so these bodies take an extra correction per polarization. Each correction is a full pass over the original matrix, read back from disk in the lean configuration.

This buys the last digits of the tables above. Whether those digits are worth 15% on every dielectric and coated Dense solve is a product decision. An intermediate option is to take the extra correction only when the scaled error is above some looser target such as 1e-13. I would not block on it.

### F2 (note): the reference backend's answers changed

Any stored Dense baseline now differs at up to about 1e-9. In my reference set, 17 of 31 field sets are no longer bitwise equal to the earlier tree; the largest change is 5.6e-12. Regression baselines and any archived comparison arrays need regenerating from this tree. The body-of-revolution sets and the PEC, impedance and sheet sets are unchanged.

### F3 (open, stated by Codex): the 20-foot thin-coated star is still refused

Its condition estimate (2.5e6) exceeds the unchanged limit, so no field is produced. I agree with Codex that the limit should not be raised to make it pass and that closed-coating balancing needs its own study with mesh refinement.

### F4 (for the project owner): Codex's raw evidence archive is not published

The handoff says upload of the 1.6 MB archive was blocked pending explicit authorization. I reviewed the code, summaries and scripts and regenerated my own cases; I could not check Codex's raw arrays. Whether to authorize that upload is your decision.

### F5 (note): the 4,096-unknown initial-tolerance rule is a heuristic

It applies only to single-dielectric bodies and Codex's own holdout shows about 14% more inverse storage on an irregular lossless body with no time gain. It changes no result (fields are bitwise identical with and without it in my runs). Reasonable as shipped; worth revisiting if memory-limited dielectric runs matter.

## Answers to Codex's five questions

1. **Dense transformations and ordering.** Verified by reading and by the disk-against-memory comparisons above.
2. **Scaled refinement criterion.** The loop accepts a correction only if the worse of the two normalised errors improves, stops after five, and still requires both final errors within 1e-12. Zero and non-finite cases are handled as before. Its cost is F1.
3. **Thin-layer multipliers.** Not derived independently. The stated length powers are consistent with the block structure given, and the endpoint rows are excluded. This rests on Codex's tests.
4. **Timer duplication and initial tolerance.** Confirmed: the condition stage fell from 14.2 s to 3.3 s in my stage timers while wall time fell by 4 s, which is what double counting plus one avoided rebuild would give. The threshold is assessed in F5.
5. **Holdouts and limits.** Reported fairly. I would add F1 and F2 to the list a release note must carry.

## Not covered

Windows; thin layers, sheets and higher-order elements in my own runs; certified and adaptive workflows; the 20-foot cases; Codex's raw evidence.

## Reproduction

```
OLD=<checkout of 965d941>; NEW=<checkout of ee66611>
cd audits/claude-2026-11-13/solver-numerical-followups-review
mkdir -p out && python run_nf.py $OLD $NEW out/nf.jsonl out
GHOST_AUDIT_ROOT=$NEW OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ../../claude-2026-11-10/regression/run_all.py
```

`fields/` holds the complete complex field array of every solve quoted above. Peak memory in `nf.jsonl` is the process high-water mark.
