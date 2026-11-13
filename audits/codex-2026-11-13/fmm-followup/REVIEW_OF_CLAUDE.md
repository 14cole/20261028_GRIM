# Review of Claude's FMM investigation

Reviewed first: `audits/claude-2026-11-13/fmm-investigation/REVIEW_AND_FMM_INVESTIGATION.md`, pinned to `claude/festive-keller-nj5bje` commit `fe0a8eb785d6697b9b008e45798ab48eda311f43`. The report blob is `6e67b3d1ca85ae262210b461b24fc2b73d89ad0d`. All 24 downloaded audit blobs were checked against their Git object hashes. The evidence archive includes those source files and results.

## Overall judgment

The prototype is useful evidence that a reusable FMM can save memory and that independent incident angles can run concurrently. Keeping Dense and Compressed is the right present decision. The results do not establish a production FMM accuracy contract, a GHOST speed crossover, or desktop capacity for layered dielectric models. No production integration is recommended by this review.

## Findings requiring correction or qualification

1. **The 181-angle headline combines different runs.** Section 2.5 correctly records 387 s for a 181-angle process run, measuring only the parent, and 1.30 GiB for a separate 16-angle thread run. The summary combines them into one apparent 181-angle time/memory result. Children must be counted. For forked processes, summing RSS double-counts shared pages; proportional set size (PSS) across the process tree is a better physical-memory approximation. Our follow-up measures both and includes a full 181-angle threaded run.
2. **The physical-size shorthand uses nominal radius.** `curve('star')` has radius `a*(1+0.3*cos(5*t))`. Thus `a=10 ft` gives a 26-foot circumscribing diameter, not a body confined to a 20-foot circle. `ka=1150` is reproducible and meaningful; the “20-foot at 18 GHz” conversion needs the radius convention. Our Galerkin large-body tests use `r=(3.048/1.2)*(1+0.2*cos(5*t))` metres, bounded by a 20-foot circumscribing diameter; those are a different star and must not be compared as identical geometry.
3. **3.9× speedup is a measurement, not a promise.** Four workers share memory bandwidth and compete with instrumentation. Our repeated measurements and unmonitored controls appear in the handoff. Threaded work remains attractive, but default worker and batch counts should use a measured workspace budget. Linux fork's sharing is not evidence for Windows spawn.
4. **The claimed diagonal-FMM accuracy ceiling is implementation-specific.** Higher expansion order can increase cancellation for close translation boxes. Wider near separation is another option, and a low-/high-frequency hybrid is a published approach. We test a wider separation, complex passive wavenumbers and gradients. Sampled product agreement near machine precision still does not certify every geometry, every right-hand side, or the final field.
5. **Condition certification requires more than ordinary products.** Estimating `||A||*||A^-1||` needs inverse actions (normally additional solves) and appropriate transpose/adjoint actions, plus usable norms or bounds. A few `A*x` evaluations do not deliver the exact induced 1/∞ norms used by existing residual normalization. The provided prototype implements neither a full inverse-norm estimator nor a general adjoint. A sampled residual can miss bad rows. Retaining the existing numerical guarantees requires an explicit and independently checked certification design; a GMRES tolerance is not a substitute.
6. **Angle rank and iteration findings have limited scope.** The observed rank saturation versus nominal `ka` is specific to the geometry, half-circle angular interval, sampling and threshold. It is not a universal rank formula. The PEC combined-field iteration counts do not predict TE transmission, coatings, corners or tightly spaced interfaces. Failure of one projection warm-start method is not proof that every recycled Krylov method fails.
7. **The 80–90-angle crossover is not established.** It mixes different geometries, bases, quadratures, tolerances and formulations. No Automatic routing threshold should be derived from it. Same-mesh and same-accuracy end-to-end Dense/Compressed/FMM comparisons are still required.

## Code observations

- `max_leaf_points` is accepted by the original FMM constructor but unused. Leaves stop at a wavelength-based depth. Refining the mesh at fixed frequency can therefore make directly stored near interactions grow quadratically. Thin layers and geometric clustering expose the same limitation.
- The `bytes` counter is partial plan-array accounting, not peak process RAM or a safe admission estimate. Temporary point/angle expansions, Krylov vectors and construction buffers matter.
- The original angle study archives RCS magnitudes but not phase-bearing fields, and postchecks a subset of angles with the same approximate operator. Our reruns retain complex amplitudes and independently recompute sampled direct rows for every angle, in addition to fresh FMM residuals for every angle.
- `Scatterer` product counters are mutable shared state in threaded use; they should not become production telemetry without synchronization or per-worker aggregation. The numerical plan arrays are read-only during products.
- The original single-layer log correction is a smooth-curve Nyström discretization, not GHOST's piecewise Galerkin singular quadrature. It cannot simply be used on corners or substituted for the existing mesh basis.
- None of these findings changes the production backend: the submitted files are research under `audits/` only.

## Reproduction of Claude's validation

The unchanged `validate.py` rerun reproduced the conclusions: point errors from about 7.2e-13 to 1.1e-9 at 4,000–64,000 points; circle RCS converged at the expected third-order rate; dense same-discretization density errors were approximately 2.9e-10 for the star and 2.2e-9 for the cavity. See `claude-validation-rerun.log` in the archive. This validates the stated narrow prototype, not untested physical configurations.
