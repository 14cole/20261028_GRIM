# Review plan, before fresh runs

Pinned Claude b0e2ba064d6b6d02d6682fac9f35947d3d2fcb38. I have read its
report and sources; this is not blind validation. No production changes.

1. Rerun Claude's guard tests. Independently demonstrate the compensated-rank
   failure and a rank-direction check (e columns, v rows) without claiming a
   product-error theorem.
2. Measure actual NumPy allocation scratch in an aliased Node.solve_into;
   compare with the prototype's 1 MiB. Observe uncharged live Woodbury arrays
   across intervening steps. Correct research scratch to the existing
   conservative bound and explicitly carry the live correction into guards.
3. Serial fresh physical solves: original sequential packed at 640 MiB;
   corrected matched run; corrected unpacked at 676; packed retry at 626;
   rank-aware guard at 640; threaded partial-TM; tighter inverse tolerances
   1e-10 and 1e-12. All 180 monostatic angles, original gates unchanged.
4. Count refinement steps per call and phase. The production counter is
   cumulative, so 9-10 total steps must not be interpreted as one slow solve.
5. Explicit normal, transpose and adjoint tests, aliasing, fallback, injected
   cancellation and guarded-memory failure with released references.
6. Cross-check complete arrays with prior fresh Dense anchors and Claude's
   hashes, label saved-reference comparisons clearly, preserve all records.

No speed claims from single runs; no artificial weakening of either storage
or live-RAM guards. No evidence archival work during physical solves.
