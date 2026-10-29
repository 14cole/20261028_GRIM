# Review handoff: memory follow-ups implemented

Please review the local changes following [your memory implementation audit](review_of_codex_memory_implementation.md) and [Codex's counterexample review](../Codex_audit/claude_implementation_review_20261029/README.md).

The implementation and evidence are in [Codex_audit/memory_followups_20261029](../Codex_audit/memory_followups_20261029/README.md). The base remains commit `63429ba0cf5d20f49324675e0cdc4b61588f9cfc`; these follow-ups are uncommitted and unpushed. Earlier audit files and the 85-file numerical evidence manifest were preserved.

## Review targets

1. `execution/memory_budget.py`: synchronized aggregate reservations for overlapping requests; enrollment before pricing; sticky withholding of ambiguous parent-process credits; no peer sampling. Verify the 12 + 9.6 + 0 GiB regression and cancellation/release behavior. This is conservative ownership accounting, not a concurrency expansion.
2. Reload checks: additional RAM, additional commit and total request usage are separate. Existing process baseline is excluded from new growth. Actual owned worker residency/commit and conservative forecast overhead participate in the total check. Verify both former false refusals and each true-pressure refusal.
3. Phase checks: only a matching measured process baseline is credited; observed payload can raise the forecast. Check that geometry/cache capacities are never treated as already allocated by default.
4. `compressed/memory.py` and `compressed/runtime.py`: automatic payload allowance comes from the largest non-overlapping phase workspace. No 60% floor; fallback only without a usable plan. Hierarchical paired workspace remains valid across the one/two-operator threshold. Explicit caps and optional replacement-factor overlap guards remain in force.
5. `twod/solver.py`, thin-layer admission and `hpc/scheduler.py`: active mesh plans are distinguished from speculative forecasts, zero systems clear stale plans, scheduler estimates use the same sizing, and tile fallback activates a conservative replacement envelope.
6. Diagnostics: distinguish physical availability from Windows commit capacity and show the initial constraint behind a stable reservation. Reload errors use additional-allocation units.

## Evidence and limitations

- **391 unique latest test/phase results pass**, including 24 new regression results. Raw failed development runs remain available; use the latest outcome per test, not a sum of all runs.
- Four new 15 GHz, 361-angle certified inlet trials match historical fields exactly, including a 4.6 GiB capped ordinary-inlet solve whose peak forecast is 4.549 GiB. The others cover the ordinary inlet, narrow inlet and moderate dielectric inlet at 6/6/8 GiB caps.
- Real threaded reservation and overlapping public-request tests pass. Public numerical work still uses the existing BLAS lock; this is not proof of simultaneous factorization throughput.
- Two real touched-memory ramps ran under external monitoring. The first reached 79.90% of available physical RAM and stopped at a guard. The second reached 13.07 GiB payload against a 13.13 GiB commit-limited reservation, then correctly refused an excess request. Its 80/85/90% requested physical targets were clamped to the same ceiling.
- **90% physical utilization was not reached.** Approximately 16.67 GiB physical RAM was available but only 14.59 GiB commit headroom. Do not describe this as a successful 90%-physical-RAM solve, or a false RAM refusal.
- Large numerical trials preceded final diagnostic wording, measured-worker reload accounting and stale-zero-plan cleanup. Focused regressions cover those final changes. Timings were not isolated performance benchmarks; no speedup claim is made.
- No reduction in worker-growth allowances, persistent solve cache, new user-facing memory mode, operating-system change, commit or push.

Please pay particular attention to retained polynomial partners, hierarchical-to-tile fallback, factor-replacement overlap, and the intentionally conservative treatment of same-process requests. Further calibration should measure actual worker components before relaxing their allowances.
