# Independent review and next investigations for Claude

Review `HANDOFF_FMM_HYBRID_CORRECTIONS.md` first. This branch contains research
changes only; all production content is unchanged. Please separate reproduced
measurements, code inspection, and untested predictions in your response.

1. **Review the straight-side repair.** Reproduce the square and mixed
   straight/curved cases with compression active. Inspect `safe_cross.py` for
   tiny nonzero components, zero sampled components that become nonzero in later
   probes, finite rejection, and physical-unit scaling. The zero sample is not
   a proof that a component vanishes. Consider fail-closed guards in the reusable
   production `cross_approximation` API; first establish which production callers
   can actually generate pathological tolerances. Do not infer production
   exposure solely from the raw routine's synthetic failure.

2. **Independently isolate the far-expansion accuracy limit.** Reproduce the
   stadium's full K/K′ matrices, digits 10/12/14, separation 2/3, and native
   targeted-column control. Increasing order worsens Frobenius error here.
   Investigate a roundoff-aware separation/translation criterion and validate
   it on tree-depth transitions, loss, multiple contours and graded supports.
   Separation 3 barely clears 1e-12 on the stadium; it is not a universal margin.
   Compare stable reusable wideband translations with the diagonal plan rather
   than promoting a numerically fragile default based on average errors.

3. **Audit actual compressed preconditioning and ownership.** This now uses
   HMatrixOperator/HMatrixSystem, not dense LU of an approximated matrix. Review
   scaling, the deliberate preconditioner-only relaxation of the operator gate,
   outer residual checks, exact sampled rows, and the absence of a dense capacity
   reference. Verify that dropping `inv.operator` is safe for forward, transpose
   and adjoint application and does not hide a retained reference or permit
   unsupported rebuilds. Inspect actual inverse bytes and construction peak.
   A lower inverse tolerance is not directly equivalent to your SVD cutoff.

4. **Challenge the end-to-end baseline comparison.** Rerun the 8,192-unknown TE
   case with Dense, existing Compressed, and FMM plus the loose inverse in fresh,
   otherwise idle processes. Include construction, solves, residual checking,
   retained memory and peak RSS. Repeat at fixed points per wavelength as k and
   panel count increase together (for example k=80/160/320 with 4,096/8,192/16,384
   panels, subject to measured admission limits). Do not extrapolate fixed-k
   refinement to a 20-foot, 15-GHz model or promise a 32-GB capacity from one case.

5. **Run physically complete hard geometries.** Prioritize a real thin coated
   PEC body and a multilayer dielectric transmission system, then high contrast,
   low-loss/resonant shapes and severe grading. The two concentric curves tested
   here qualify primitive operators only, not a physical coated-body solve.
   Check complete fields against Dense and an analytic reference where available.
   Include both polarizations and distinguish mesh error from solver error.

6. **Investigate construction and sweep economics.** The global inverse helps
   iteration counts, but preparing a second operator costs time. Prototype a
   bounded near-query cache or compress panel blocks then fold their factors
   into nodal bases. Account repeated kernel calls and the cache's peak, not only
   final factors. Compare 1/16/181-angle workflows with shared/batched products.
   Examine whether H²/HSS inverse structure or a global coarse correction can
   improve the existing Compressed backend enough to avoid a separate FMM
   production backend. Native persistent wideband plans remain a distinct task.
   Also test retaining the small exact validation-row cache from preconditioner
   construction instead of querying those rows again. For real exterior k only,
   target panel moments should be conjugates of source moments: investigate
   sharing that table with tiled conjugation, while preserving separate tables
   for lossy interior k. These are unmeasured follow-ups, not claimed savings.

The existing Dense and Compressed release gates must remain intact. A promising
research preconditioner is allowed to be inaccurate internally only when an
independent accurate outer solve verifies the result. Please identify any gap
between the research checks and the production acceptance/condition pipeline.
