# Which methods remain under consideration?

The objective is a reliable solver workflow that uses less RAM and time. FMM is currently the leading matrix-free research candidate, not a commitment to replace Dense or Compressed. The latest round specifically audits an FMM prototype because its earlier results warranted independent checks.

## Next comparison: hybrid versus wideband

Claude's hybrid is worth prototyping: retain exact singular/very-near integration, compress geometrically separated local interactions with existing H-matrix machinery, and use the reusable FMM for more distant interactions. This is still an FMM-based hybrid; it also reuses the Compressed backend's main strength.

It is a design proposal, not a measured RAM or time improvement. Several details matter:

- Current FMM leaves are at least 1.5 wavelengths when the ordinary tree is active. Their interactions are not all subwavelength. Compression must recurse by geometry and wavelength; small frequency alone does not make a touching/near-singular block low rank.
- The partition is by panel pairs, while a continuous P1 node belongs to multiple panels. A DOF-distance mask would not automatically reproduce the prototype's exact near/far split.
- Reusing compression and approximate-inverse primitives is plausible. The inverse of a masked near operator is not automatically the existing global Compressed inverse, and inverses of local pieces do not simply sum to its inverse. Include the mass/jump terms, material coefficients, adjoints and scaling.
- A smaller product near field need not force an identically smaller preconditioner. Product and preconditioner partitions can be chosen separately, or supplemented by a coarse global correction. This trades RAM/setup for convergence; weakening is a risk to measure, not an automatic theorem.
- Adaptive wideband FMM attacks the same crowded-leaf storage problem through stable low-frequency translations. With bounded occupancy and controlled interaction lists it can bound local storage; it does not by itself bound Krylov/preconditioner memory or guarantee few iterations.

Use the same Galerkin mesh, quadrature policy and physical accuracy for both prototypes. First compare a fixed-frequency refinement series and a thin-gap/coated case. Then compare full solves at 1, 16 and 181 incident angles, including setup, inverse/preconditioner construction, true residual checks, peak process RAM and failures. A fast matrix-vector operation is only one term in the total.

## Alternatives beyond FMM

| Direction | Evidence so far | Why keep it or deprioritize it |
|---|---|---|
| Existing direct Compressed backend; improved hierarchical factors | Already part of the workflow; factors amortize across incident angles | Keep as a baseline and a potential preconditioner. Multi-angle reuse can beat iterative FMM even when individual products are cheap. |
| Directional H² / nested compression | Literature-backed candidate; no new GHOST implementation benchmark | Worth retaining as a larger architectural alternative, especially for shared bases and many-angle direct reuse. Factorization complexity and high-frequency ranks need evaluation. |
| Selective complex64 inverse factors | Previous research reduced inverse payload 36–38%, but operator-plus-inverse retained storage only 11–13%; peak RAM did not consistently improve | Smaller and nearer-term than a new engine. Construct factors directly in the intended precision and qualify refinement/fallback before claiming capacity gains. |
| Disk-backed residual matrix | Previous complete-solve study measured roughly 1.2 GiB peak versus 2.2 GiB for its in-memory case | A useful capacity tool already investigated. It is residual storage, not out-of-core factorization, and it leaves factor RAM and arithmetic costs. No general SSD timing claim. |
| Dense correction-loop tuning | Previous paired dielectric tests averaged about 10% less time with an experimental intermediate target; coated timing was inconclusive | A possible modest speed improvement, not a large RAM solution. Final quality gates must remain intact. |
| Better formulations/preconditioning | Near-block ILU converges where simple controls fail, but factors are large relative to the tested small system | Essential across iterative/hybrid methods. Geometry/material conditioning is not cured by storing the same operator more cheaply. |
| Mesh/order adaptation and geometry-aware refinement | Established workflow concept; no new savings measured in this review | Reducing unknowns can be valuable, but must preserve physical field accuracy. The current research FMM is P1-only and cannot establish savings for high-order meshes. |
| Full out-of-core LU or a global FFT/grid method | No demonstrated win in the current evidence | Lower priority than the measured bottlenecks: dense cubic work/I/O remain, and detailed boundaries can make FFT padding/interpolation costly. |

The earlier non-FMM figures above come from `../solver-methods-research/HANDOFF_SOLVER_METHODS_RESEARCH.md` in this branch's ancestry; they were not rerun as part of this review. They are case-specific measurements, not universal performance promises.

## Recommendation

Keep both existing production backends and one Automatic workflow. Resolve/standardize the operator-accuracy details, then run a bounded hybrid-versus-wideband experiment with a preconditioner designed alongside it. Keep the smaller Dense/Compressed improvements available as separate work. Do not choose an engine from point-product timings or assign a percentage saving to an unimplemented hybrid.
