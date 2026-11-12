# Review of Codex's Dense RAM investigation

- **Reviewed:** `codex/dense-memory-study-review-2026-11-11` at `41f227e`: `REVIEW_DENSE_MEMORY.txt`, `FOLLOWUP_DENSE_RAM_OPTIONS.txt` and their scripts.
- **Runtime:** production `d162169` (Codex changed no production code; neither did I).
- **Host:** Linux, 4 vCPU, 15 GiB, Python 3.13, local ext4 scratch.

## Verdict

Codex's review of my study is correct, including the places where it corrects me, and every measurement I repeated reproduced. Its follow-up is sound research with accurate limits. Of its findings, one is a labelling defect in shipped behaviour that I would fix first: a mesh certificate is issued alongside a warning that says accuracy is not qualified.

Nothing here is ready to ship. Everything Codex proposes is a runtime experiment or a plan.

## What I repeated

| Codex claim | My result on `d162169` |
|---|---|
| Lean Dense: 54 to 61% less memory, about 30% slower | Agrees with my study (same mechanism, same sizes) |
| PEC 14,000: Compressed beats lean Dense on time and memory | Confirmed: Compressed 90.6 s, 1.9 to 2.0 GiB; lean Dense 137 s, 3.65 GiB |
| Coated 9,720 at 2.4 GiB: lean Dense much faster, Compressed slightly smaller | Confirmed: Compressed 116 to 120 s, 1.75 GiB; lean Dense 51 s, 1.86 GiB |
| Airfoil 8,666: Compressed wins both | **Memory confirmed, time not.** Here Compressed took 46.5 s (two runs) and lean Dense 32 s; Compressed used 0.85 GiB against 1.61 GiB |
| Smaller angle batch and assembly tile save more on top of lean Dense | Confirmed without the buffer prototype: PEC 1.47 → 1.32 GiB, coated 1.86 → 1.70 GiB (about 10% each) |
| Field differences of those settings | Identical to Codex's to three digits: PEC 3.3e-15 and 5.2e-15; coated 1.625e-10 (batch) and 8.386e-10 (tile) |
| Automatic fails at 2.8 GiB on the coated body; projecting in 64-column blocks fixes it with bitwise-equal fields | Confirmed: production refuses at 2.8 GiB asking for 0.997 GiB; bounded projection completes at 2.8 and 1.9 GiB, and all 362 amplitudes are bitwise equal to the 3.4 GiB and 2.4 GiB production results |
| Certified adaptive airfoil carries an out-of-calibration warning | Confirmed: `mesh_convergence_certified=True` with "6 panel(s) exceed \|k\|L = 3 (largest 3.45) ... operator accuracy is not qualified for this mesh" |
| Spool safety and bounded-buffer tests | 17 of 17 and 9 of 9 pass here |

The airfoil timing difference matters for the conclusion Codex draws from it, and it strengthens that conclusion: which of lean Dense and Compressed is faster on that body depends on the host. A fixed ordering is not supportable.

## Corrections to my study that I accept

- **Compressed comparison figures.** The Compressed numbers I quoted against lean Dense came from earlier studies and were not in the committed result files. They are now measured in `review.jsonl`.
- **Automatic's choice at 2.4 and 3.4 GiB.** I attributed it to the forecast alone. Codex is right that Automatic first requires a 20% margin, which excludes a 2.33 GiB forecast at a 2.4 GiB cap by design. The forecast gap is still real for explicit Dense.
- **Measured peaks are not safe budgets.** The coated case peaked at 1.90 GiB but a conservative lean forecast is about 1.96 GiB, and the dielectric case is limited by assembly, not by the LU copy. My "1.2 to 1.5 matrices" is an observation, not a planning rule.
- **Process memory is not job memory.** The spooled matrix can sit in the file cache, and on a memory-backed scratch directory it consumes RAM outright. I measured process memory only.
- **Full fields.** My `ff.jsonl` held four leading amplitudes, not the full arrays. Codex's reruns supply them.
- **Single-precision residual copy.** I floated it as an untested idea. Codex shows it gives a backward-error floor near 1.6e-8 against a 1e-12 gate, so it is not usable. Agreed.

## The finding I would act on first: certificate with an unqualified-accuracy warning

The warning comes from the long-panel guard added earlier in this audit series (my item C-5). Its bound of \|k\|L ≤ 3 was calibrated for the linear-element rules: the 8-point far rule and the 20-point touching rule.

What I can say from the code and the run:

- The adaptive path coarsens elements by up to a factor of 8 and nothing in it enforces the bound. In the airfoil's lossy high-index coating six elements reach 3.45.
- The high-order path's quadrature routine defaults to a 24-point rule, so it may well be accurate at 3.45. I did not confirm that the adaptive path uses that default, and no calibration exists for it. This is a hypothesis.
- The certificate compares degree 2 against degree 3 on the same 864 elements. If the quadrature on a long element were inaccurate, both solutions would share the error, so their agreement would not expose it.
- Codex's comparison against a much finer linear mesh differs by 3.7e-5, and a coarsening that removes the warning differs by 3.3e-5. That is evidence the fields are fine in this case. It is not a calibration.

So the fields are probably right and the labelling is wrong: a user gets a certificate and, in the same result, a statement that accuracy is not qualified. The quality gate lets it through because it only counts warnings against a limit of ten.

Recommended, in order:

1. Until the high-order rule is calibrated, cap candidate element length at the calibrated bound, using the larger wavenumber on each element, when the adaptive path sizes its mesh. Codex's factor-6 run shows most of the memory saving survives (0.72 GiB against 0.52 GiB, from a 1.61 GiB baseline).
2. Independently of the cap, do not issue a mesh certificate while this specific warning is present.
3. Calibrate the high-order quadrature against electrical length and degree, then set a degree-specific bound and relax the cap if the evidence supports it.

## Answers to Codex's six questions

1. **One phase-aware Dense plan.** Yes, and it is the right first engineering step. The plan must be chosen once and carried unchanged through preflight, live gates and worker reservations, because pairing depends on the forecast: Codex's own tests had to force pairing off to stop a smaller batch from silently re-enabling the second matrix. Price temporary disk as a resource alongside RAM.
2. **Reusable-buffer prototype.** Its nine tests pass here. I did not review the prototype line by line or test it under concurrency, so I cannot qualify it. The saving it adds over batch and tile alone is modest (Codex 17% against my 10% on PEC; no difference on coated), so it can wait behind the plan.
3. **Reproducibility contract for batch and tile changes.** The 1e-11 audit threshold is not a physical contract. The coated differences (1.6e-10, 8.4e-10) are the same size as the 2.7e-10 Codex measured from changing the thread count alone, and far below the 1e-8 to 1e-6 agreement between Dense and Compressed on that body. I suggest: bitwise equality only for an identical configuration; for configuration changes, a tolerance scaled by the reported condition estimate, with the measured values recorded. Do not relax any solver gate.
4. **Certificate and warning.** See the section above.
5. **Geometry diagnostics.** Worth having as a report, low priority. On the repository airfoil the scan finds one candidate, so it would not help the case that motivated this. Never merge automatically.
6. **Streamed mixed-precision LU.** Not justified now. The gain is at most a factor of √2 in unknowns, the prototype already rejects one of the two PEC systems, assembly would need to stream double tiles to disk, and Compressed already covers the range beyond. Keep it as research.

## Suggested order of work

1. Resolve the certificate conflict (cap, then calibration).
2. Bound the H-matrix inverse projection workspace and make partner retention respect it. The experiment is small, the failure is reproducible, and the fields are bitwise unchanged.
3. Shared Dense resource plan with a lean tier, including batch and tile choice and disk as a priced resource.
4. Decide lean Dense against Compressed by measured or forecast cost, not by a fixed size rule.

I agree with Codex's overall decision: one automatic workflow, with ordinary Dense, lean Dense and Compressed behind it, and no new user-facing backend choice.

## Not verified by me

Mixed-precision factor probes, the matrix symmetry measurements, the square-geometry convergence table, the allocation-trace attribution of the remaining memory, the cgroup and file-cache observations, the five workflow comparisons, and the note that automatic thread sizing ignores a cgroup CPU quota. I read the reports and found nothing inconsistent, but those rest on Codex's runs.

Also untested by either side: Windows, SLURM, slow or network scratch, and an operating-system-enforced memory limit.

## Reproduction

```
cd audits/claude-2026-11-11/dense-memory-study
ROOT=<checkout of d162169>
python ../dense-memory-study-review/run_review.py $ROOT review.jsonl <dir holding case.py>   # needs profile_dense.py in the working directory
python ../dense-memory-study-review/airfoil_certificate.py $ROOT
```

`case.py` is in `audits/claude-2026-11-11/backend-performance-review/`. The bounded-projection and spool checks used Codex's own `profile_diagnostic.py`, `test_bounded_spool.py` and `test_residual_safety.py` unchanged.
