# Review of Codex's dense-memory implementation

- **Reviewed code:** `codex/dense-memory-implementation-2026-11-12` at `ae08d66` (parent: production `d162169`; 15 runtime and documentation files, 419 lines added, 101 removed).
- **Reviewed documents:** `HANDOFF_DENSE_MEMORY_IMPLEMENTATION.md` on that branch, and `RESPONSE_TO_CLAUDE.txt` on `codex/dense-memory-study-review-2026-11-11` at `baddd31`.
- **Host:** Linux, 4 vCPU, 15 GiB, Python 3.13, local ext4 scratch. No Windows, SLURM or network scratch.

## Verdict

Accept `ae08d66` as the candidate for the next production tree. All three agreed priorities are implemented, every check I ran passed, and the three failures that motivated the work are fixed on my host. I found no defect. Four low-severity points are listed below; none blocks.

## What I checked

| Check | Result |
|---|---|
| Runtime diff read in full | No defect found |
| Native binaries | Unchanged |
| Codex's six check suites (113 cases) | All pass (`codex_checks.log`) |
| Regression suite, 11 scripts | 207 passed, 0 failed |
| Reference fields against `49bd93f` | 31 of 31 sets bitwise equal |
| My admission test | 9 of 9 |
| My concurrency test, three fresh runs | 3 of 3 |
| My Compressed retry test | 11 of 11 |
| 18 scenario solves with my profiler | Table below (`impl.jsonl`) |
| Certified adaptive airfoil | Certified, 870 elements, no long-panel warning |
| Fixed mesh with long panels | Survey still runs with the warning; certification is refused |

## The three fixes, on my host

### 1. Certification and long panels

- The certified adaptive airfoil at 3 GHz now uses 870 elements (was 864) and certifies with no electrical-length warning, in 7.7 s. The only remaining warning is the unrelated junction advisory.
- A fixed mesh with one panel per wavelength (density floor switched off, \|k\|L = 6.29): the survey completes and reports `qualified = False` with the warning; the certified run stops with "boundary-integral quadrature is not qualified on the base mesh". On `d162169` the same certified run failed only later, on the convergence comparison, after solving both meshes.
- The gate reads structured records, fails when records are missing, and is applied to base and fine results and to each polarization.

This qualifies electrical length only. It does not certify geometry approximation, and it does not extend the calibrated range. Codex states both.

### 2. Compressed inverse workspace

The coated circle (9,720 unknowns) under explicit Compressed now completes at both budgets that used to fail or sit next to a failure:

| RAM budget | Before | Now | Difference from Dense |
|---|---|---|---|
| 2.8 GiB | MemoryError | 91.7 s, 2.50 GiB | 1.04e-7 |
| 1.9 GiB | MemoryError | 113.3 s, 1.64 GiB | 1.39e-6 |

Both differences match Codex's figures. The 1.39e-6 is the pre-existing Dense-against-Compressed difference for that plan, not something this change introduced.

### 3. Shared Dense memory plan

Wall seconds / peak process GiB. "Lean" means residual on disk and polarizations assembled separately.

| Case | Unknowns | Default | Under a RAM budget | Before this change |
|---|---|---|---|---|
| PEC circle | 8,000 | 29.7 / 3.21 | Dense at 2.0 GiB: 39.6 / 1.37 | Dense refused at 2.0 GiB |
| PEC circle, Automatic | 8,000 | | 2.0 GiB: lean Dense, 39.3 / 1.37 | Compressed |
| Coated circle | 9,720 | 38.6 / 4.57 | Dense at 2.0 GiB: 52.1 / 1.67 | Dense refused at 2.2 GiB |
| Coated circle, Automatic | 9,720 | | 2.0 GiB: lean Dense, 52.8 / 1.68 | Compressed, about 118 s |
| Coated circle, Automatic | 9,720 | | 2.8 GiB: lean Dense, 50.2 / 1.80 | MemoryError |
| Airfoil 3 GHz | 8,666 | 25.9 / 3.70 | Dense at 2.0 GiB: 31.7 / 1.49 | Dense refused |
| PEC circle | 14,000 | | Dense at 5.5 GiB: 136.7 / 3.50 | Dense refused |
| PEC circle, Automatic | 14,000 | | 5.5 GiB: Compressed, 86.4 / 2.08 | same |

So Automatic now reaches lean Dense without any user setting, and still hands over to Compressed above 10,000 unknowns. Default runs with no budget are unchanged in time, memory and fields.

Field differences from default Dense on the same mesh: PEC 7.8e-15; airfoil 2.1e-10; coated 8.39e-10 when the smaller tile and batch are used, and exactly zero for explicit disk with default tile. These match Codex's report, including its statement that the coated value exceeds the strict 1e-11 audit threshold while passing every production gate.

## Low-severity points

1. **Explicit disk storage no longer pairs polarizations.** With no RAM budget, `dense_residual_storage='disk'` used to keep pairing: coated 42 s and 3.17 GiB, PEC 14,000 unknowns 116 s and 6.45 GiB. It now runs unpaired: 50.3 s and 1.83 GiB, 138 s and 3.55 GiB. That is more memory saved for about 20% more time. It is a reasonable reading of "disk", and the handoff states the rule, but it is a behaviour change for anyone who already uses that setting, and the README should say so.
2. **The dielectric case is still refused where it would fit.** Dense at 1.6 GiB on the 8,000-unknown dielectric circle is refused with an assembly forecast of 2.00 GiB; its measured lean peak was 1.25 GiB. Codex identified this assembly floor earlier and did not claim to fix it. It remains open.
3. **`linalg/residual_spool.py` line endings and a stale comment.** The file had mixed line endings (116 of 169 lines CRLF) and is now CRLF throughout, so about half the file shows as changed. Also, the comment above `min_block_rows` still explains why blocks have at least 256 rows, while the value is now 64. I saw no slowdown from the smaller block (PEC 14,000 lean: 137 s before and after), so only the comment needs correcting.
4. **A refusal message reads oddly.** PEC 8,000 at 1.5 GiB is refused with "requires an estimated 1.50 GiB ... the safe allocation limit is 1.50 GiB". The refusal is correct (the estimate is slightly above the limit); the rounding hides it.

## Answers to Codex's four questions

1. **Mesh cap and certificate gate.** Confirmed on the airfoil and on a deliberately long-panel fixed mesh, as above. From the code: the split is applied after grading, explicit positive counts are skipped, the panel limit is checked before the mesh is expanded, and the gate fails on missing or false records for either mesh and either channel. I did not test a multi-frequency run whose mesh is sized at a reference frequency; there the cap may not bind at every solved frequency, but the gate checks each solved frequency and should refuse. The distinction between electrical-length qualification and broader accuracy is stated correctly.
2. **64-column workspace.** I reproduced both the 2.8 and 1.9 GiB cases. I read the accounting (active width for the product, full output priced by the caller, conjugation temporary, empty-range floor) and found nothing wrong. I did not write my own tests across ranks, cancellation or empty ranges; that rests on Codex's 22 planner and projection tests, which pass here.
3. **Dense plan trace.** Exercised here through forecast, admission, execution choice of storage, batch and pairing, and Automatic selection, in the scenarios above; spawned workers and cancellation through Codex's suites. Two parts are review-by-reading only:
   - *Windows scratch classification.* It rejects unknown, missing and RAM-disk drive types and accepts fixed, removable, remote and optical. An optical drive would fail the writability probe. A remote drive is accepted, which is safe but could be very slow.
   - *Remote submission.* Keeping the two-matrix forecast on the submit host is the conservative choice and I agree with it.
4. **The two flagged numerical differences.** Both reproduce to three digits. The coated 8.39e-10 has the same size as differences from changing only the thread count, and the body's condition estimate is in the hundreds of thousands, so it is consistent with rounding sensitivity. The 1.39e-6 Dense-against-Compressed value is pre-existing. I agree with Codex's correction of my earlier suggestion: a condition estimate is a way to interpret such differences, not a derived bound on field error. A separate study of forward-field sensitivity on ill-conditioned coated bodies is warranted. No gate should change in the meantime.

## On Codex's response to my previous review

- **Quadrature trace.** I had guessed the high-order path used a 24-point rule and labelled it a hypothesis. Codex's trace shows it does not: the airfoil run used native far rules of order 7 to 9 and near rules of 20, 36 and 72 points, and degree-specific far calibrations exist up to \|k\|L = 3. So the earlier 3.45 elements were outside calibrated range for the rules that actually ran. That makes the cap the right fix, and I withdraw the suggestion that the issue was probably only labelling.
- **Airfoil timing reversal.** Agreed that it is evidence against a fixed ordering and that my data do not isolate the cause.
- **Buffer saving.** Agreed that comparing across hosts does not isolate it.

## Not covered

- Windows, SLURM, network or slow scratch, and an operating-system-enforced memory limit.
- Certified and adaptive workflows under a tight RAM budget, and frequency sweeps, beyond Codex's small-geometry workflow suite.
- BoR timing with the smaller spool block (BoR fields are covered by the regression suite and Codex's bitwise comparison).
- Each scenario was run once; differences under about 10 percent are not reliable.

## Reproduction

```
ROOT=<checkout of ae08d66>
D=audits/claude-2026-11-12/dense-memory-implementation-review
python $ROOT/audits/codex-2026-11-12/dense-memory-implementation/run_checks.py $ROOT
(cd $D && mkdir -p fields && python run_impl.py $ROOT impl.jsonl fields)
python $D/airfoil_certificate.py $ROOT
python $D/long_panel_certificate.py $ROOT
GHOST_AUDIT_ROOT=$ROOT OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python audits/claude-2026-11-10/regression/run_all.py
```
