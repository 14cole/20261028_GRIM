# Review of Codex's backend stress improvements

- **Reviewed code:** `codex/backend-stress-improvements-2026-11-12` at `cfe005a` (production baseline `ae08d66`; six runtime files and one document, 84 lines added, 67 removed).
- **Reviewed document:** `audits/codex-2026-11-12/backend-stress-improvements/HANDOFF_BACKEND_STRESS_IMPROVEMENTS.md`, with the earlier stress-suite handoff for context.
- **Host:** Linux, 4 vCPU, 15 GiB, Python 3.13, local ext4 scratch. No Windows.

## Verdict

Accept the three production changes in `cfe005a`. Every check passed and I found no defect in them. I found one selection quirk in Automatic that predates this commit (F1), and one error in my own regression harness that affects how earlier "207 passed" results should be read (F2). The three research items should stay research, as Codex proposes.

## What I checked

| Check | Result |
|---|---|
| Runtime diff read in full | No defect found |
| Line endings, native binaries | Preserved, unchanged |
| Codex `test_improvements.py` | 15 of 15 |
| Codex legacy checks, six scripts | All pass |
| Regression suite | 207 passed, 0 failed, after correcting my harness (F2) |
| Reference fields against `49bd93f` | 31 of 31 sets bitwise equal |
| My admission test; concurrency test, three runs | 9 of 9; 3 of 3 |
| 27 scenario solves with my profiler | Below (`stress.jsonl`) |

Wall times in this batch ran about 30% slower than earlier batches for unchanged Dense cases, so I draw no timing conclusions from it. Memory, selection and field results are unaffected.

## Change 1: explicit Compressed uses the hierarchical operator from 1,024 unknowns

This replaces the outer retry I added two rounds ago. It is the better design: the request no longer pays for a failed tile attempt first.

| Case | Unknowns | Result | Peak | Difference from Dense |
|---|---|---|---|---|
| PEC circle | 2,000 | H-matrix | 0.26 GiB | 1.7e-12 |
| PEC circle | 3,000 | H-matrix (was tile) | 0.35 GiB | 3.1e-12 |
| PEC circle | 8,000 | H-matrix, one attempt (was fail, then retry) | 1.03 GiB | 3.2e-12 |
| Dielectric circle | 4,000 | H-matrix | 0.55 GiB | 5.2e-9 |
| Dielectric circle | 8,000 | H-matrix | 1.07 GiB | 1.3e-8 |
| Coated circle | 6,480 | H-matrix, one attempt (was fail, then retry) | 1.35 GiB | 3.7e-8 |
| Coated circle | 9,720 | H-matrix | 2.49 GiB | 1.0e-7 |
| Airfoil 3 GHz | 8,666 | H-matrix | 0.84 GiB | 2.0e-10 |

With `GHOST_HMATRIX_MIN_UNKNOWNS=8192` the 8,000-unknown PEC case is rejected at the rank limit, as before. That is the user's explicit choice and the previous retry did not apply to it either.

On whether the removed retry still had a use: no. The tile path now runs only where the hierarchical operator is unsupported, below 1,024 unknowns, or after the hierarchical assembly itself was rejected. In each of those a retry at a 1,024 threshold would take the same path again.

### Change 2: single-dielectric assembly ownership

The 8,000-unknown dielectric circle, 181 angles:

| Request | Result |
|---|---|
| Dense, disk residual, 1.8 GiB | Admitted; peak 1.22 GiB; all 362 amplitudes bitwise equal to default Dense |
| Dense, automatic storage, 1.8 GiB | Admitted with disk; 3.4e-11 from default (smaller tile) |
| Dense, in-memory residual, 1.8 GiB | Refused (forecast 2.46 GiB) |
| Dense, disk residual, 1.6 GiB | Refused (forecast 1.77 GiB) |

These match Codex's figures and the 1.766 GiB I computed for this correction alone in my previous review. The discount is taken from a resource record built by the same helper the assembly uses, and unequal quadrature orders keep the extra matrix. Every caller of the resource function uses the default equal orders, and so does every caller of the assembly, so the forecast and the allocation agree on all public routes including submission planning. Submission still prices two system matrices for the solve phase.

### Change 3: compressed polarization planning

Explicit Compressed on the coated circle (9,720 unknowns) completes at all three budgets: 2.8 GiB paired (peak 2.48 GiB), 2.4 and 1.9 GiB separate (1.77 and 1.66 GiB). Differences from Dense are 1.0e-7 paired and 1.39e-6 separate, the same as before this change.

I did not construct a counterexample to the fixed-pairing logic, and I did not reproduce the 69,036-unknown plan at 24 GiB: that script reads captured resource records from Codex's evidence archive, which I did not extract. Those two parts of Codex's question 2 rest on its own tests.

## Findings

### F1 (low to medium, predates this commit): raising the RAM budget can switch Automatic from Dense to Compressed

Dielectric circle, 8,000 unknowns, Automatic, 181 angles:

| RAM budget | In-memory Dense forecast | Selected |
|---|---|---|
| 2.3 GiB | 2.46 GiB (does not fit) | Dense, lean plan at 1.77 GiB |
| 2.6 GiB | 2.46 GiB (fits the cap) | Compressed |

At 2.3 GiB the in-memory plan exceeds the cap, so the planner prices the lean disk plan, which fits with the 20% headroom, and Dense is chosen. At 2.6 GiB the in-memory plan fits the cap, so no lean plan is priced; but 2.46 GiB misses the 20% headroom (2.08 GiB), so Dense is excluded and Compressed is chosen. A larger budget gives the less preferred backend.

This also explains an apparent disagreement with the handoff, which says Automatic selects Compressed at 2.3 GiB. Codex used 19 angles, where the in-memory forecast is 2.22 GiB and fits the cap; I reproduced that too.

Both outcomes are valid solves. The inconsistency comes from the Dense plan introduced in `ae08d66`, not from this commit. Suggested fix: when the in-memory Dense plan fits the cap but misses the headroom, price the lean plan as well and offer whichever meets the headroom.

### F2 (my error): one regression script imported part of the solver from my own branch

`audits/claude-2026-11-10/calibration/w_far_rule.py` put my working tree's `tools/GHOST` first on the import path, ignoring `GHOST_AUDIT_ROOT`. `test_s1_s2_w_far_rule.py` imports it, so in that one script (36 of the 207 checks) modules loaded after that point came from my branch instead of the tree under test. It surfaced now because my branch still has the removed retry hook, which made the import fail on `cfe005a`.

I corrected the path and reran that script against `cfe005a` and against `ae08d66`: 0 failures on both. For earlier rounds (`49bd93f`, `d162169`), the far-rule checks in my "207 passed" figures were partly exercising my branch's code. The operator code those checks cover did not differ between the trees in those rounds, so I do not expect a different outcome, but I have not rerun them and they should be read with that qualification. The other ten scripts were not affected.

### F3 (note): this branch carries audit files

`cfe005a` is on a `codex/` branch with audit directories. A clean distribution branch from `ae08d66` plus these seven files would be needed before release, as in earlier rounds.

## The research items

**Closed-coating condition scaling and equilibrated Dense LU.** I agree these are the most valuable next numerical work, and that neither should ship yet.

- The Dense failure on the 18,253-unknown coated star is a backward-error failure of unscaled LU on a badly scaled matrix, and scaling the LU input is the standard remedy. The Dense factor already computes row and column equilibration vectors for its condition estimate, so a per-factor implementation has the scaling to hand; the work is in applying it to the LU input and transforming the normal, transpose and adjoint solves, while keeping the residual against the original matrix.
- A condition estimate that drops from 2.5e6 to 7e4 under a different scaling shows the gate is scaling-dependent. That is a reason to define the gate on one stated scaling, not a reason to treat earlier refusals as spurious. Codex says the same.
- Before enabling either: base and fine mesh agreement on the thin-coated geometry, deliberately near-singular controls that must still be refused, both residual storage modes, and the adaptive and certified workflows.
- I did not run these experiments.

**Loss-aware rank forecast.** Agreed: do not ship. One lossy material is not a calibration, and the lossless exterior still couples distant parts.

**Dense workspace.** Agreed: keep the conservative formula until the bound is derived from the allocating code. My measurements in the previous round support that order: the ownership correction is exact, while the workspace term is where forecast and measurement disagree.

## Answers to Codex's six questions

1. **Ownership declaration.** Matches every route I traced; no private or remote forecast inherits a discount its assembly does not earn, because all callers use equal orders by default and an unequal pair must be passed explicitly to both.
2. **Pairing counterexample.** None constructed; three live budgets pass. The 24 GiB plan was not reproduced.
3. **Explicit threshold and removed retry.** Confirmed on Linux as above; the retry no longer provides a distinct attempt. Windows not run.
4. **Workspace bounds.** Not derived by me; see my previous review for the empirical evidence.
5. **Condition normalization and scaled LU.** Assessment above; not run.
6. **Attenuation forecast.** Agree with not shipping it.

## Not covered

Windows; the 20-foot research cases; the native-disabled runs; the 143-case replay itself (I ran my own 27 scenarios and Codex's test scripts, not its full suite).

## Reproduction

```
ROOT=<checkout of cfe005a>
D=audits/claude-2026-11-12/backend-stress-improvements-review
(cd $D && mkdir -p fields && python run_stress.py $ROOT stress.jsonl fields)
python $D/profile_dense.py $ROOT '{"body":"diel","n":4000,"mode":"automatic","options":{"ram_budget_gib":2.3}}'
python $D/profile_dense.py $ROOT '{"body":"diel","n":4000,"mode":"automatic","options":{"ram_budget_gib":2.6}}'
GHOST_AUDIT_ROOT=$ROOT OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python audits/claude-2026-11-10/regression/run_all.py
```
