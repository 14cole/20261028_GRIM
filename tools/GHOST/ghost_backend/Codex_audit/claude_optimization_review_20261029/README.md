# Review of Claude's optimization follow-up audit

Reviewed `Claude_audit/review_of_codex_optimization_followup.md`, the current implementation, saved trial summaries, source hashes, the original A/B script, source-encoding checks and prior impedance qualification. This round ran only a small synthetic accounting reproducer. No production code was changed, no full suite or end-to-end solve was launched, and nothing was pushed.

## Main finding: the exact recheck still misses a false refusal

Claude's overall endorsement is too broad. The main optimizations and measured results remain supported, but the claim that the detailed recheck prevents conservative worker-RSS refusals misses another branch of the resident calculation.

In `execution/memory_budget.py`, `require_reload()` takes the maximum of:

- Numeric ownership plus the largest modeled overhead / worker residency / worker private-commit value.
- Parent RSS growth plus worker residency.
- Parent private-commit growth plus worker private commit.

The exact-recheck shortcut at line 314 requires worker RSS to exceed both modeled overhead and worker private commit. That only considers the first branch. The second branch can dominate even when that condition is false, because the parent process's RSS and private growth differ. Shared or mapped resident pages can produce such a difference.

**Synthetic reproduction, all values in GiB:** reservation 3.5; live available RAM 8; numeric payload 0.5; parent RSS growth 3; parent private growth 1; worker RSS 1; worker private commit 1.5; worker unique residency 0.1; requested additional allocation 0.2. The cheap check charges 4 GiB and refuses without refining, because 1 is not greater than 1.5. A detailed reading charges 3.1 GiB and correctly admits the request with 0.4 GiB remaining allowance. A second case shows the same omission when modeled overhead suppresses the retry. A genuine-capacity-failure control still refuses even with a detailed sample.

`reproduce_refusal.py` and `verification.json` preserve the reproduction and confirm that all six source/test hashes still match the audited final follow-up. These are injected accounting observations, not a demonstrated failure during the saved physical inlet trials and not an allocation of GiB-sized arrays.

**Recommendation before push:** remove or correct the shortcut that looks only at `max(overhead, worker_commit)`. A simple conservative implementation is one detailed retry for a reservation-bound refusal whenever a cheap worker charge was used; retain the one-retry guard, fresh OS checks and genuine refusal afterward. Add regressions covering parent-RSS dominance, overhead dominance, and genuine rejection. This rare-refusal path need not add work to successful allocations.

## What I agree with

- Keep bounded construction observations, explicit consumable reload allowances, useful diagnostic retention, and the cheaper live worker probe. The new finding concerns a remaining false refusal, not unsafe admission or changed field accuracy.
- Keep the junction compatibility guard. The routing/interpolation mismatch is algebraic, and declining optional reuse correctly preserves independent assembly. That does not mean the incompatible projection formula itself has become valid.
- Run the full suite on the final corrected revision before the next push. The prior pushed revision did not have a clean full-suite run. The local follow-up's 184 tests and 27 subtests are focused validation, not a substitute.
- The estimated under-1% residual overhead is plausible but unmeasured. Subtracting the separate-session increments suggests roughly 0.54 seconds; different host throughput and harness conditions prevent treating that as a controlled result. A same-session A/B would measure it for this inlet, but two repetitions per arm may still be insufficient to establish a sharp 1% threshold if noise is comparable.
- Successful inlet comparison fields are bit-identical. Concurrent fields are instead equal to within floating-point roundoff, at most about 4.28e-15 in the three reported trials. Claude's later concurrency table states this correctly; its opening "every run" wording is too broad.
- The worker-sample telemetry note is valid. A zero unique-residency value in a cheap sample means that quantity was not measured for credit, not that the workers use zero unique RAM. Clarify this in report text; if retaining full samples for calibration, keep a separate bounded request-local list without extra sampling or persistent history.

## Corrections to the proposed follow-ups

### ASCII-source cleanup

Merely excluding audit files or narrowing the check to production would not make the current suite green: seven checked production files still contain non-ASCII source, including the material parser, launchers and UI. Preserve Unicode input support through ASCII escapes where appropriate, and maintain the GHOST/FREDDY shared-parser contract. Earlier encoding-only edits were reverted because changing only one parser copy broke that contract. Do not remove coverage simply to obtain a green result; an intentional exclusion for historical snapshots is a separate test-scope decision.

### A/B harness

The original seven-module control remains conceptually appropriate. However, Claude's old `inverse_checks_ab/ab.py` still recursively sums duplicated construction records, the issue already established in the earlier review. Its timing is unaffected, but its reported check counts are wrong. It also refuses to run while its existing `runs/` directory is present. Use a fresh output location, preserve historical evidence, record final-source hashes, and count only the canonical execution-system builds. The corrected harness in the construction-efficiency audit is a better starting point than rerunning the old script unchanged. No new A/B was started during this review.

### Impedance and concurrency qualifications

The surface-impedance override is a useful experimentally supported alternative for the tested strongly absorbing material, not a generally validated substitute for the full 12-foot 15 GHz bulk solution. There is no matching full-size bulk reference at that frequency, and moderate weak-loss material was a negative control with large errors. Keep the approximation explicit and preserve that accuracy boundary.

The GUI disables starting another job while its solver/density worker is active. The two-request concurrency result qualifies the tested scripted same-process workload. It should not automatically be transferred to every HPC driver or scheduling arrangement; those use their own worker and reservation paths.

## Recommended order

1. Fix the missed exact-recheck boundary and add the targeted regressions.
2. Clarify the mixed worker-sample report and resolve source-encoding/test-scope issues without losing material compatibility.
3. Run the full suite once on the final revision; investigate remaining failures before claiming a clean push.
4. Optionally run the corrected, same-session inlet A/B to measure residual overhead. Do not make an unverified under-1% claim a prerequisite for correctness.
5. Shift further numerical work to coated conditioning/rank behavior and magnetic discretization/forecast scaling. The current trials do not establish arbitrary-material capacity under 32 GiB.
