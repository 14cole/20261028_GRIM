# Independent Dense/Compressed research plan

Parent: 27afe8f3fb523a0a61f2a99ebb77e9e2708f16d7. No new Claude review is
required or consulted for these hypotheses. Production sources stay unchanged.

1. Compressed: pack completed inverse-node off-diagonal factors to complex64
during recursive construction, leaving leaf/correction LU double. Compare
baseline, post-build packing and construction packing. Retained bytes alone
are not a peak-memory result. Measure stage RSS/high-water RSS, construction
accounting, setup, refinement cost and accepted physical solutions. Detect
and retain failures, rebuilds, overflow/underflow and adjoint discrepancies.
2. Dense: compare full residual multiplication with bounded row-block products,
with/without contiguous copies. Keep every existing physical/scaled residual
gate. Investigate batching and 180/360 angles, and requested thread counts.
3. Expand validation beyond the smooth star: PEC, dielectric, PEC-backed
coating, two dielectric layers plus PEC core, and complex narrow geometries.
Use production formulation/condition paths where feasible, preserve rejection
results, and state geometry dimensions/materials and actual unknown counts.
4. Scale promising cases to larger unknown counts within the actual 16 GiB
cgroup. Do not pretend to measure a 32 GB desktop or bypass RAM admission.

Accuracy: retain complex densities/RHS/fields; compare matching cases against
Dense with field 1e-8 and density 1e-7 relative gates, plus unchanged production
and fresh exact-row checks. Test transposed/adjoint inverse solves separately.
Run numerical jobs serially in fresh processes. Repeat decisive controls.
Publish scripts, raw evidence, positive and negative outcomes, and limits.

Next Claude handoff: independently formulate hypotheses/checks before adopting
our conclusions, then cross-analyze matched evidence. Label fresh runs versus
array replay/source inspection. Agreement between models is not validation.
