# Review of ecc046c and inverse-upgrade lifecycle repair

Claude's review identifies a real production performance defect. I reproduced
it, repaired one production file, and independently exercised the repair with
native solves, condition estimation, rejected-hint fallback, operator
tightening, and cancelled-build recovery. Numerical acceptance gates remain
unchanged. The gather-v2 and sequential-construction proposals remain separate;
this branch does not promote them into production.

Reviewed commit: `ecc046c21a480c5534e32f987e05f013bda84271` on
`claude/festive-keller-nj5bje`, specifically
`audits/claude-2026-11-16/sequential-readiness-response/REVIEW_OF_SEQUENTIAL_READINESS_REVIEW.md`.
Baseline and parent: `cbcf3bff24f6ab392d38a576187cfb2a23fbad20`.
Repair branch: `codex/inverse-upgrade-lifecycle-2026-11-16`.
All 26 files in Claude's review directory were retrieved at the pinned commit
and verified against their Git blob identities; see `source-provenance.json`.

## Finding and repair

`CompressedFactor._upgrade_preconditioner()` previously consumed its optional
upgrade attempt once for the lifetime of the factor object. An ordinary
`_fresh_build()` can replace the upgraded inverse with the weaker initial
inverse, but left that attempt consumed. Later solves could therefore pay
eight refinement corrections indefinitely instead of two on the tested slot.
This happens without cancellation and with either construction order.

The one-file change is in `tools/GHOST/ghost_backend/compressed/factor.py`:

- Successful ordinary `_fresh_build()` completion permits one optional upgrade
  for the newly built inverse, including the successful hint early-return path.
- Failed admission, failed compact retry, and interrupted construction do not
  reset the attempt state.
- Rejected-hint recovery explicitly calls `_fresh_build(allow_upgrade=False)`.
  It continues to suppress the immediate upgrade that could repeat the failed
  route. A later ordinary fresh build can again permit an attempt.
- `_build()` itself does not reset this state. Refinement retries and optional
  upgrades therefore cannot repeatedly re-arm themselves.

This is a private lifecycle-policy correction. No user options, numerical
tolerances, defaults, memory-admission rules, native libraries, or Dense code
change. A successful upgrade can retain a larger inverse: 46,610,456 bytes
instead of 43,342,560 bytes in this slot, about 3.1 MiB additional retained
storage. Existing replacement, payload, and live-memory guards still apply.
This repair reduces repeated correction work; it is not a whole-process RAM
reduction or a claimed universal wall-time speedup.

## Independent computations

`PLAN.md` records the plan before our new physical runs. First I reran Claude's
`claude_slot_attribution.py` unchanged against the original code. Its sequence
reproduced: first solve 5 corrections, stable solve 2, then 8 and 8 after a
fresh build inside the same object. The weaker rebuilt density differed from
the strong control by 1.728175917141004e-9 in maximum per-angle relative L2
error, while satisfying the exact-row gate. That script installs gather v2.

I then wrote and ran `run_slot.py` without either research gather or build-order
hook, demonstrating that the bug and repair also occur in production code.
Ten fresh processes completed successfully, preserving 41 complete field-solve
results, including a separate Dense reference. Each solve preserves densities,
right-hand sides, fields, angles, sampled row indices, row norms and residuals.

The physical case is the inherited thin dielectric slot: 1,024 P1 panels,
2,048 unknowns, TE, epsilon = 3 - 0.08j, mu = 1, free-space k = 20 per geometry
length unit. It uses either 16 or 180 monostatic incidence angles from -90
inclusive to +90 exclusive. The 180-angle cases request condition estimation.
Every solve is checked against 96 fresh exact coefficient rows selected with
seed 2026111609. This is an algebraic lifecycle test on one geometry, not a
new full-scale GHz/model-size benchmark or mesh-convergence study.

Corrections counted in each public field solve:

| Case | Initial | Stable | Rebuilt | Rebuilt stable | New factor, same operator |
|---|---:|---:|---:|---:|---:|
| Original, 16 angles | 5 | 2 | 8 | 8 | 5 |
| Fixed, 16 angles | 5 | 2 | 5 | 2 | 5 |
| Original, 180 angles + condition | 2 | 2 | 8 | 8 | 2 |
| Fixed, 180 angles + condition | 2 | 2 | 5 | 2 | 2 |
| Original, operator tightening | 5 | 2 | 10 | 8 | 5 |
| Fixed, operator tightening | 5 | 2 | 7 | 2 | 5 |
| Fixed, cancel then recover | 5 | 2 | 5 | 2 | 5 |

Condition estimation can consume the upgrade before the first field solve;
that explains the initial count of two in the 180-angle cases. The tightening
count includes the pre-rejection solve and the nested solve after rebuilding:
10 = 2 + 8 originally, 7 = 2 + 5 with the repair.

For every fixed ordinary, cancellation and tightening case, the final recovered
density, RHS and field match a fresh factor on the same final operator bit for
bit. The different tightening operator is compared to its own fresh factor,
not assumed identical to the initial operator.

Across all 41 solves, including original-code controls:

| Accuracy measure | Maximum |
|---|---:|
| Per-angle density relative L2 error versus Dense | 1.385133534928095e-9 |
| Field error divided by peak Dense field magnitude | 3.5100778676668245e-14 |
| Exact sampled-row normwise backward error | 3.4198513617074298e-15 |

All RHS arrays match Dense exactly. All stated gates passed. Dense and
Compressed share the native formulation, so this checks algebraic agreement,
not independent physical or discretization correctness.

## Safety-path validation and scope

The hint test injects a successful strong hint and then one refinement
rejection. This invokes the real production rejected-hint path. Both original
and fixed code build exactly `[1e-10, 1e-8]`, with no extra upgrade; both later
solves take eight corrections, and their density/RHS/field arrays match bit
for bit. This protects the intentional suppression policy.

The tightening test injects one failed sampled-row check, then delegates to
the original sampler. The real `HMatrixFactor.inverse()` path rebuilds the
operator at tenfold tighter tolerance and reconstructs its inverse. Subsequent
gates remain real and unchanged. This proves the caller's behavior, but does
not measure how often real geometries trigger that path naturally.

The cancellation test raises an `InterruptedError` subclass at the fourth
checkpoint inside the inverse-child-product construction guard during an
in-object rebuild. The consumed attempt remains consumed on failure; the
inverse is `None`, abandoned inverse weak references die, pending construction
bytes return to zero, no product workers survive, and the executor context
resets. A successful subsequent fresh build re-arms and recovers exactly.
This is one controlled phase with a memory ledger, not a rerun of all 48
Claude cancellations or a GUI/native-stall cancellation test.

Nine focused tests in `test_upgrade_lifecycle.py` additionally cover the real
lifecycle methods with controlled builder/admission fixtures: one attempt per
successful generation, denied upgrade suppression, hint fallback scope,
hint early return, failed admission, failed compact retry, fresh-build
cancellation, coarse-rejection fallback, and restoration of the old inverse
and budget on optional-upgrade cancellation. All nine passed.

The host has a 16 GiB cgroup limit and a four-CPU quota. The physical suite
uses two assembly threads, one BLAS thread, an 8 GiB requested ledger budget
and a 4 GiB factor/operator storage allowance. It is not a real-pressure
32 GiB desktop test. `environment.json` separately labels the probe process's
default BLAS pool and the actual physical-test thread settings.

## Cross-analysis of Claude's review

I agree with Claude's explanation of the lifecycle issue and with the accepted
qualifications about inverse policy and above-threshold construction. Its
reported cancellation outcomes are consistent with the published records.
`review_records.py` independently recomputes 48 cancellation/recovery outcomes
across eight processes, verifies cleanup fields, and locates precisely the
two nonidentical in-object slot recoveries. This is record verification, not
48 fresh reruns by Codex.

Two evidence limits remain explicit:

- Claude's low-level cancellation harness has no memory ledger, so those
  records cannot establish pending-construction-byte cleanup. Our new native
  case checks it with a ledger for one targeted phase.
- Although Claude's script saves control NPZ files locally, this commit does
  not publish them or a cross-thread density-hash manifest. Consequently its
  cross-thread bitwise-determinism statement and full cancellation-array
  comparisons cannot be independently replayed from this commit alone. I
  accept them as reported fresh computations, not as independently replayed
  array evidence. Claude also explicitly disclosed that its replay of our
  preceding evidence archive was blocked by its command runner.

The previous recommendation to integrate gather v2 and corrected sequential
construction, scoped to `HMatrixSystem` and aligned diagonal query allowances,
still stands. This focused repair does not implement that separate proposal.
The 64k, real-pressure, Windows, GUI-abort, stalled-native-call, larger-threaded
build and operator-memory questions remain open; these tests do not close them.

## Evidence and reproduction

See `README_REPRO.md` for exact commands. `analysis.json` contains every solve's
metrics and array hashes; `results/` is reconstructed from the five archive
parts and `evidence/MANIFEST.json`. `out/slot_attribution.json` is our unchanged
rerun; `claude/out/slot_attribution.json` is Claude's separately pinned result.
Raw timing/process logs are included without claiming a percentage speedup.

The evidence pack contains 41 NPZ datasets and 40 raw records/logs. Restoration
verifies compressed payload and full-archive hashes. The final verification
checks every original/restored array bit and C/F layout, every record byte,
and exact equality of the original and replayed analysis JSON. See
`evidence-verification.json` and `final-verification.json` for completion counts.
`production-change.patch` applies cleanly to the baseline. The source inventory
has 277 unchanged files and this one changed production file among 278 checked;
publication additionally verifies the complete parent Git tree.

## Requested independent review by Claude

Please write your independent expectations and tests before using our harness
as the only oracle, then cross-analyze your results against the complete arrays
and records here. In particular:

1. Check whether one attempt per successful ordinary fresh build is the correct
   lifecycle policy for all `CompressedFactor` callers and subclasses. Challenge
   the explicit rejected-hint suppression and the decision not to reset in
   `_build()` itself.
2. Independently exercise ordinary rebuild, condition-probe upgrade, rejected
   hint, failed admission/compact retry, and cancellation. Confirm no retry loop
   or lost old-inverse/budget restoration. Try an alternative geometry that
   naturally upgrades, and trigger operator tightening naturally if feasible.
3. Verify the complete evidence archive and compare densities/fields at matched
   final operators and inverse policy. Explain any cross-machine rounding
   differences rather than assuming universal bitwise identity.
4. Publish the missing control arrays or cross-thread hash manifest for ecc046c,
   and finish the prior archive replay. Extend ledger-enabled cancellation to
   other phases if needed; do not treat the record audit here as that experiment.
5. Keep gather/sequential integration and its larger-scale/platform validation
   separate from acceptance of this small production repair. Measure the
   operator-memory bottleneck and real-pressure behavior before claiming the
   overall Compressed workflow is ready at 64k or on every desktop.
