# Stored-basis FMM review and independent reproduction

Reviewed Claude commit `0328f1fde93a63062ea9938cfff154a8893b2730`.
Parent Codex commit `9ce0f99e362c99313e27b0637fbca196d853a09a`.
Branch: `codex/fmm-stored-basis-review-2026-11-15`.

**The final-preconditioner recombination diagnosis reproduces.** In the fresh
8k/180-angle comparison, stored Z reduced compute by
15.3% and accurate operator
applications by 11.6%, with peak
process memory changing from 0.428 to 0.448 GiB.
It still took 8.8 times the fresh
Compressed control's compute time. This is one paired comparison, not a
statistical speedup guarantee. Production remains unchanged.

## Fresh measurements

| Case | Compute seconds | Solve seconds | Peak GiB | Accurate RHS-equivalent applications | Cycles | Nonconverged true checks |
|---|---:|---:|---:|---:|---:|---:|
| star-8192-180-compressed | 46.83 | 4.16 | 0.701 | — | — | — |
| star-8192-180-v3 | 484.03 | 394.96 | 0.428 | 3704 | 46 | 23 |
| star-8192-180-z | 410.08 | 322.55 | 0.448 | 3276 | 23 | 0 |
| square-1024-180-TE-z | 19.28 | 2.75 | 0.121 | 1084 | 23 | 0 |
| slot-1024-180-TE-z | 20.69 | 8.07 | 0.133 | 1968 | 23 | 0 |
| slot-1024-180-TM-z | 17.85 | 4.66 | 0.132 | 1444 | 23 | 0 |

Seven fresh physical cases completed, including the separate instrumented
eight-angle diagnostic: **1,088 incident columns**. Every case passed comparison
with the archived Dense reference. Maximum peak-normalized field difference:
3.448e-12; maximum
per-angle density relative L2 difference:
1.047e-10. Maximum saved
exact-row backward error: 4.110e-15.

The fresh 16-row check of Claude's supplied 32k/24 density passed with maximum
backward error 1.748e-17. This is an independent
equation check, not a newly timed 32k solve. The new 8k v3 solution agrees with
Claude's supplied v3 density to
7.018e-12
maximum per-angle relative L2 difference.

The local evidence archive restored 49
numerical arrays bit for bit, and the restored analysis matched exactly.
All 278 production file hashes remained
unchanged. See `analysis.json`, `independent-checks.json`, `fresh-row-check.json`,
`source-provenance.json`, `archive-verification.json`, and `README_REPRO.md`.

## Verdict and what changed

Claude identified a real finite-precision inconsistency in the research right-
preconditioned block solver. I independently confirmed it with a physical
equation diagnostic, fresh full-angle controls and complete density/field
comparisons. Stored preconditioned basis vectors are the preferred validated
research variant for these cases. This is not a change to the shipped solver.

The old candidate was `x + M(VY)`. Arnoldi had actually used the separately
computed blocks `Z_j = M(V_j)`, so the consistent candidate is `x + ZY`.
These expressions are mathematically equivalent for a fixed linear M, but the
computed actions need not agree at the requested 1e-12 residual tolerance.
The stored-Z form is the usual flexible right-preconditioned GMRES construction.

I accept Claude's correction to the earlier restart explanation: at 32k,
restart 20 hides the mismatch by refreshing the residual before projected
convergence. Its new longer-restart controls expose it. The earlier observation
that the 20-step cap is reached remains correct, but it was not a complete
diagnosis of the behavior at longer restart lengths.

## Independent mechanism check

Before reading the new report I recorded competing hypotheses in
`INDEPENDENT_CHECK_PLAN.md`. I had seen the commit file listing, including a
stored-Z filename. The numerical checks were designed independently but executed
after reading Claude's report; this is not a blind replication claim.

In a fresh 8,192-unknown, eight-angle diagnostic, the same first-cycle basis and
least-squares coefficients gave:

- Projected relative residual: about 6.12e-13.
- True relative residual using recomputed `M(VY)`: about 3.56e-11.
- True relative residual using stored `ZY`: about 6.12e-13.
- Direct residual from the saved operator actions `AZ`: about 6.12e-13.
- The equation effect of `M(VY)-ZY`: about 3.56e-11.
- Accurate-operator linearity discrepancy in this comparison: about 6.47e-16.

This directly isolates the final preconditioner recombination, rather than
inferring a cause merely from two cycles or a speed improvement. The relative Frobenius-norm
difference between the two computed preconditioner corrections was 3.40e-11.
The diagnostic intentionally stores extra arrays and performs extra operator
applications. Its timings and original Krylov-capacity counter are not benchmark
measurements of either production-sized research variant.

### Qualification: the inverse is not stored in single precision here

I enumerated every array reachable from the retained inverse tree in that run:
**187 complex128 arrays (81,317,824 bytes) and 63 int32 pivot arrays**. No
complex64 inverse arrays were present. The construction operator uses packed
complex64 blocks, but it is released before the accurate FMM solve. The retained
inverse application, scaling and inputs in this case use double precision.

Therefore Claude's inference that the effect is consistent with mixed-precision
**retained inverse storage** should be corrected. Finite-precision inconsistency
is confirmed; locating which inverse-tree operations amplify roundoff is still
open. The Woodbury correction/subtraction is a plausible place to instrument,
not a demonstrated root cause. Lower precision during construction can affect
the resulting preconditioner's quality/conditioning, but that is different from
applying a single-precision inverse or having a changing mathematical operator.

Independent dense tests deliberately used both double- and single-precision
preconditioner arithmetic across three random seeds, with duplicate/zero RHS.
All 12 solutions passed a fresh true-residual check and a dense reference.
The single-precision controls reproduce the mechanism: v3 needs a corrective
second cycle, while stored Z converges in one. The double controls converge in
one cycle with either method. These synthetic controls demonstrate a mechanism;
they do not imply that the physical inverse is single precision. Both solvers
also passed all-zero tests.

## Scope and numerical safeguards

The full paired star sweeps use 4,096 panels / 8,192 unknowns, k=80, 180 incident
angles from -90 through 89 degrees, width 8, restart 20 and preconditioner
tolerances 1e-4. Their enclosing diameter is 30.56 free-space wavelengths.
Square TE and thin-slot TE/TM checks each use 512 panels / 1,024 unknowns, k=10
and the same 180-angle grid. They are about 3.18 wavelengths wide; the slot is
1% of body width and 75% of body height.

All are 2D P1 single-interface dielectrics with epsilon_r=3-0.08i and mu_r=1,
surrounded by free space. They are not finite 3D, multilayer, PEC, or realistic
20-foot models at 15–18 GHz. The true scaled FMM residual target remains 1e-12;
field/density comparison gates remain 1e-8 and 1e-7. Independent coefficient-row
backward errors must stay below 1e-12. Production uses backward-error checks,
which are not interchangeable with this FMM relative-residual target.

Stored Z does not justify dropping true residual checks. Deflation, finite-
precision operator products, ill-conditioned cases and variable preconditioners
can still make projected estimates unreliable. The geometry tests do not certify
mesh convergence or condition numbers. Every fresh case retains full complex
densities, RHS, fields, angles and row-validation arrays in the evidence archive.

The two full FMM runs and the Compressed control are single fresh-process runs,
serial and one thread. Small unit tests were performed while the instrumented
diagnostic was running, before the timed full sweeps; the diagnostic is excluded
from performance conclusions. No other numerical experiments ran alongside the
timed controls. Times are individual observations, not confidence intervals.

## Cross-analysis of Claude's evidence

Claude's raw JSON reproduces the reported 8k work counts: 3,884 accurate
RHS-equivalent applications for v2, 3,704 for v3, and 3,276 with stored Z.
The v2-to-v3 reduction is the predicted 180 applications from removing duplicate
restart checks. Zero-RHS trigger handling is also corrected; physical plane-wave
RHS are nonzero, so that fix does not account for these physical speed gains.

Its 32k results are **24-angle probes**, not full stored-Z sweeps. At restart 20,
both v3 and stored Z use 768 accurate applications and two cycles per block.
Stored Z eliminates the recombination gap but cannot eliminate an insufficient
iteration budget. At restart 40, stored Z uses 696 applications and one cycle
per block; v3 uses 840 and two cycles. This supports the causal explanation and
shows why restart length must be considered together with the update formula.

The capacity cost is explicit: at 8k/restart 20, V alone takes 21 MiB and Z adds
20 MiB. At 32k/restart 40, V takes 164 MiB and Z adds 160 MiB. Comparing that
combined 324 MiB with the old restart-20 V-only 84 MiB includes **both** storing Z
and doubling restart length. Claude's measured 32k peak rises from 1.672 to
1.821 GiB at matched restart 40, or from 1.560 to 1.821 GiB when also changing
restart 20 to 40. These are process peaks, not total desktop memory forecasts.

I did not rerun Claude's 32k solves. I downloaded and Git-blob-hash-verified the
newly supplied 8k/180 and 32k/24 density archives, checked their declared array
hashes, and recomputed their sampled backward errors. The 8k full density and
field comparison against the archived Dense reference is now independently
replayable. I additionally regenerated 16 new exact coefficient rows, disjoint
from Claude's published rows, for its 32k/24 density and checked all 24 RHS.
This is fresh equation validation of a supplied solution, not a fresh 32k solve.

The full 32k/180 reference densities and some stored-Z outputs remain unpublished.
Hashes and norms are useful provenance, but do not permit an independent density
comparison. Split those original arrays into sub-100-MB parts before temporary
storage expires; user authorization to include an evidence archive is already
present. Avoid rerunning expensive cases solely because recoverable evidence
was not preserved.

## Next handoff: independent checks, then cross-analysis

The user explicitly requests independent checks before joint conclusions.
For the next review, record your own hypotheses and verification plan before
adopting this response's interpretation. Independently reproduce the claims that
would change the implementation or backend recommendation, then compare code,
assumptions, full accuracy evidence and matched work/time/memory measurements.
State which results are fresh solves, fresh equation checks, reanalysis of saved
arrays or another model's measurements. Neither shared code nor model agreement
is an independent reference by itself; retain dense/reference comparisons and
new coefficient checks. Resolve disagreements explicitly.

Priorities:

1. Review the double-precision inverse census and the direct equation-level
   diagnostic. Distinguish confirmed recombination inconsistency from the still
   unmeasured location of its roundoff amplification inside the inverse tree.
2. Keep stored Z as the tested research approach with explicit memory accounting
   and unchanged true-residual acceptance. A possible memory-saving experiment
   is to replay the original preconditioned basis blocks during the final update,
   using identical block shapes, instead of applying M to their sum. This costs
   extra preconditioner work and requires independent accuracy/performance tests;
   it is a proposal, not a measured improvement here.
3. Preserve the remaining full evidence arrays. A full 32k stored-Z sweep can
   establish its actual gain, but do not extrapolate 24 angles into a completed
   benchmark or make it a prerequisite for retaining the current backends.
4. Prioritize the 32 GB desktop memory boundary and Dense/Compressed memory
   improvements for the user's 180–360-angle workload. FMM still needs a clear
   memory-capacity use case; these results do not establish a speed crossover.

No production module, GUI control, or shipped DLL/SO changed in this response.
