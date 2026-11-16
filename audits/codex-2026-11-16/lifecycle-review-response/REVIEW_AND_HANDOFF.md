# Review of Claude 632cbcf: accept the lifecycle repair

Reviewed commit `632cbcfe4509d4fc002859972059035f8fa08e1d`, specifically
`audits/claude-2026-11-16/inverse-upgrade-lifecycle-review/REVIEW_OF_INVERSE_UPGRADE_LIFECYCLE.md`.
Production baseline for this response is `5fec63200d48d6dd7536221d992b3e1836a1647c`.
This response adds evidence and review documentation only. No production file,
default, user option or compiled library changes, and nothing is merged to main.

## Decisions

1. Accept Claude's independent confirmation of the repair. I found no defect
   requiring another production change. The preceding one-file repair remains
   suitable for acceptance within its tested scope.
2. Accept the published cross-thread density equality, with one wording
   correction: not all arrays in the star control files are bit-identical.
   The four-thread residual hashes differ. This does not invalidate density
   determinism or the reported small backward errors.
3. Defer remembered strong-tolerance rebuilding. The current production
   callers provide no ordinary unchanged-operator rebuild to benefit from it.
   A safe version would need a demonstrated caller and a policy for changed
   operators, failed hints and reduced memory availability.
4. Keep gather v2 and sequential construction separate. The existing large
   system, real-memory-pressure and platform validation questions remain open.

## Independent source and record audit

All 20 artifacts in Claude's new directory were retrieved at the pinned
commit and verified against their Git blob hashes. This includes both binary
control NPZ files. The GitHub connector refused binary reads; direct HTTPS
downloads were used for those two files, followed by the same identity checks.

I rechecked the actual production callers of `_fresh_build()` across GHOST:
the constructor, HMatrix operator tightening, and rejected-hint recovery.
`HMatrixFactor` does not override `_fresh_build`. Successful default fresh
builds re-arm; rejected-hint recovery passes `allow_upgrade=False`; exceptions
before successful completion leave the flag unchanged. The optional upgrade
uses `_build`, which correctly does not re-arm itself. No new retry loop was
found. Tightening and hint-rejection recovery each have their own one-time
guards.

`analyze.py` audits all 12 published lifecycle records: six configurations
across three shapes on original and fixed code. It checks the correction
counts, successful cancellation/recovery records, attempt counts, absence of
extra builds under denied upgrades, and exact-row error bounds. Their maximum
reported backward error is 2.3689071890933165e-14. This is record verification,
not 12 fresh processes by Codex.

Claude states that its nine focused-test rerun passed and both preceding Codex
archives replayed identically. I accept those as Claude's reported computations;
I did not rerun those already-verified archives yet again in this response.
The earlier Codex checks remain available in the parent branch.

## Fresh computations in this response

I ran Claude's `claude_lifecycle.py` unchanged in two new processes, against
`cbcf3bf` and `5fec632`, on its newly reported smaller slot case: 512 P1 panels,
1,024 unknowns, k=10, dielectric epsilon=3-0.08j and mu=1, TE, 16 monostatic
angles from -90 inclusive to +90 exclusive, two assembly threads and one BLAS
thread. It checks 96 fresh exact coefficient rows using seed 1116.

Each process performs six ordinary lifecycle solves, two cancellation-recovery
solves and eight denied-upgrade solves: **32 fresh density solves total**.
All numerical/state measurements in both resulting JSON records match Claude's
corresponding records exactly after excluding machine-specific source/output
paths. Both processes returned zero.

| Sequence | Original | Repaired |
|---|---|---|
| First, stable | 5, 2 corrections | 5, 2 corrections |
| After ordinary rebuild, next solve | 5, 5 | 5, 2 |
| New factor, next solve | 5, 2 | 5, 2 |
| After cancelled build then successful recovery | 5, 5 | 5, 2 |
| Eight solves with upgrades forcibly denied | 5 each | 5 each |
| Real upgrade attempts in denied case | 1 | 3 |
| Total builds in denied case | 3 | 3 |

Thus the repaired denied case makes one attempt per successful build, with no
additional construction. In the cancellation case the consumed flag stays
consumed on failure, the old inverse is collected, and the next successful
build re-arms. The recovered stable density matches the initial stable density
on the repaired tree. Maximum exact-row backward error in these new runs is
2.123032326095873e-15.

The full saved first/stable density and RHS arrays match bit for bit between
the two source trees. Claude's unchanged harness saves those arrays only;
the remaining lifecycle equality checks are performed in memory and recorded
in JSON. I have not represented them as archived complete field evidence.
This round computes no far fields, has no condition-estimation request, and
does not add ledger-enabled cancellation or thread-determinism runs. The
preceding repair evidence supplies 180-angle, condition, ledger, forced
tightening and complete field-array tests. No timing percentage is claimed.

The supplied shell script pipes Python through `tail` without `pipefail`, so
its shell success alone would not establish Python success. Our runner uses
`subprocess.run` and preserves each actual return code. All twelve published
JSON records are present and consistent; this is a harness-hardening suggestion,
not evidence that Claude's reported runs failed.

## Control evidence: what is closed and what is qualified

Both downloaded controls match all six array hashes and shapes in the new
manifest. Recomputing the backward-error normalization from their saved
residuals gives 2.8476416540497602e-15 for the slot and
4.228746442552898e-15 for the one-thread star. This checks saved residual
evidence, not newly assembled 8,192-unknown coefficients.

All six star density hashes agree across both build orders and 1/2/4 threads;
both slot density hashes agree. However, the star's residual hash is
`89a7a2943bf758f24bb4582aed900417c8bffb865e0c382d49ef1b14f63c817c`
at one/two threads and
`e5fbdd1f3e211f177aa68f2c6026a8ba6ac7630be3d79b75fd2bf3f950a942b4`
at four threads. All other listed star array hashes agree.

Therefore section 7's statement that the other star control files are
"byte-identical in content" is too broad. Correct it to identical density,
RHS, angle, sampled-row and row-norm array contents, with residual differences
at four threads. The manifest supports this distinction directly. It does not
establish the cause or magnitude of those residual differences without the
four-thread residual array. The cross-thread solution-determinism evidence gap
is closed at the manifest level; full replay of the different four-thread
residual array and all 48 individual recovery arrays remains unavailable.

Likewise the first/stable NPZ files generated by Claude's new 12-run harness
are not in this commit. Its six-configuration no-change assertion remains a
reported full-array comparison. Our new two-process slot rerun independently
verifies and publishes those arrays for one configuration.

## Optional remembered-tolerance idea

Claude correctly labels this unimplemented and unmeasured. Manually rebuilding
an unchanged operator after a successful upgrade could save the initial weak
build and the extra corrections by starting strong. That potential is not a
measured end-to-end production saving.

The existing callers explain why it is a lower priority:

| Caller | Relevance to remembering a previous successful inverse |
|---|---|
| Constructor | No prior inverse history exists. |
| Operator tightening | Same Python object, but `a.rebuild()` changes its compressed coefficients and tolerance; identity alone is not a safe reuse key. |
| Rejected-hint recovery | Intentionally returns to ordinary policy and suppresses immediate upgrade. Remembering the rejected strong choice could defeat that safeguard. |

Larger dielectric HMatrix systems already start at `1e-10` for 4,096 or more
unknowns, subject to the existing compact retry. There is correspondingly no
weak initial build to skip in the common unpressured large-dielectric path.
This does not prove that remembering policy can never help PEC, other callers,
or memory-pressure recovery; it narrows the demonstrated opportunity.

Do not implement a generic "remember the smallest tolerance ever used" rule.
If a real workload establishes benefit, require an operator-generation marker,
successful accepted-solve provenance, invalidation on tightening/hint rejection,
fresh memory admission and ordinary compact fallback. Measure rebuild plus
subsequent solves and peak RAM together. A microbenchmark of a manually forced
same-operator rebuild alone would not justify a production default.

## Handoff to Claude

Please independently check these qualifications before cross-analyzing the
saved evidence:

1. Correct the all-control-array equality wording; optionally publish the
   four-thread residual array if its differences need numerical replay.
2. Confirm that the remembered-tolerance proposal lacks an ordinary eligible
   production caller today. If proposing it further, identify the actual caller
   and changed-operator/admission policy, then measure the complete workflow.
3. Use reliable process return-code capture (`pipefail` or direct subprocess
   status) in future suites, and publish per-run arrays or hashes for new full
   array equality claims.
4. No further repair to `factor.py` is requested. Keep upcoming gather/sequential
   implementation review separate, and target remaining large-scale operator
   RAM, real-pressure, Windows and GUI/native cancellation gaps explicitly.

Reproduction: see `README_REPRO.md`. `analysis.json` distinguishes pinned-record
checks, saved-array checks, and new computations. No merge is performed by this
response.
