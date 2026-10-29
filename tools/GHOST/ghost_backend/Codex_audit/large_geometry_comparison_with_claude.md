# Comparison of large geometry audits

Date: October 29, 2026.

Claude's [large-geometry audit](../Claude_audit/large_geometry_ram_speed_audit.md) correctly identifies material wavelength, additional interface unknowns, facing walls and active-factor residency as major limits. The new [Codex audit](large_geometry_ram_speed_audit.md) adds ten completed solves and twenty-five current-code forecasts. Its measured inlet examples strengthen the capability assessment while narrowing several of Claude's extrapolations.

| Topic | Agreement or correction |
| --- | --- |
| Material effects | Strong agreement. Metal, homogeneous dielectric and coated-metal bodies must be distinguished. The new high-contrast test is a homogeneous TYPE 3 body, not Claude's assumed coated PEC duct. Neither can establish a universal coated-inlet GHz limit. |
| Metal inlets are easy throughout the band | Too broad. The tested 10 GHz metal contours pass, but the narrow inlet needs 10,563 unknowns and about 74 seconds after refinement, versus an initial 3,216-unknown candidate. Other cavities, details and resonances remain untested. |
| Concavity is supported | Supported by the existing quadrature/formulations and the new successful reentrant-contour solves. Keep numerical gates; do not infer that all cavities pass from these examples. |
| Relax the condition gate for cavities | Not recommended on the current evidence. A small residual/backward error does not imply small forward error for an ill-conditioned problem. Any revised acceptance policy needs independent references and conditioning-sensitive field-error evidence. |
| Keep incompressible blocks dense | Already partially implemented: H-matrix assembly can store dense interaction lists, dense hierarchical factors have a bounded dense-leaf fallback, and compressed inverse nodes up to 512 unknowns can become dense leaves. The remaining inverse-rank issue requires an admitted hybrid-node strategy, not just storing an operator block differently. |
| Spill compressed operators | Worth developing, but the present polarization spool loads all active tiles back into memory. True active-block streaming must cover products, inverse access, caches, temporary storage and failure cleanup. Spilling the operator alone does not eliminate the inverse's storage requirement. |
| Correct conservative forecasts | Agree on matched calibration, not a blanket downward multiplier. New refinement increases the required system size, and historical jobs exceeded their budgets. The high-contrast test demonstrates substantial conservative rank forecasts, but neighboring refused cases are still unmeasured. |
| Reciprocal H-matrix assembly | Promising speed work. Existing reciprocal kernel infrastructure can help, but adaptive queries need coordinated reuse and mixed-material matrices must not be assumed symmetric. No demonstrated universal 2x gain yet. |
| Mixed-precision LU with a disk original | Possible development option. The single-precision factor is half the size of a double factor; reaching one quarter of the two-double-matrix footprint also requires avoiding a resident double assembly copy throughout the relevant peak. Current residual-spool eligibility is double precision, so this is not already a working option. |
| Lower the dense/HODLR threshold to 6,000 | Still requires measured crossover qualification across workloads and thread counts. The new stronger-preconditioner experiment has direct evidence of a larger improvement on one demanding material case. |
| Geometric reflection symmetry | Worth exploring for fully symmetric geometry and material equations. Ideal half-size system arithmetic is not an existing measured GHOST improvement, and both parity sectors are needed for general incidence. |
| Out-of-core LU using 4,000–8,000-wide panels in a few GB | The suggested sizes do not fit that claim at N=127,000: one full-height panel alone is 7.57–15.14 GiB. Smaller blocks are possible, but disk traffic, pivoting, factor storage and work buffers must be designed and benchmarked. |
| Unlimited desktop size and fixed runtime predictions | Unsupported. Out-of-core computation remains limited by disk capacity, I/O, arithmetic, conditioning and practical time. The proposed 14 hours on one node or 15–30 minutes on eight nodes are not measured runtimes for these geometries. |
| Current HPC distributes one matrix | It does not; it distributes independent geometry/frequency jobs. A distributed factorization needs additional MPI/library integration. |
| Directional compression solves frequency growth | It can improve oscillatory operator representation. It does not guarantee that every inverse or cavity Schur complement remains low rank, nor that RAM becomes frequency-independent. |

The principal difference in priorities is the capacity strategy. Claude favors out-of-core dense LU early. Codex favors first reusing the existing H-matrix product with a smaller preconditioner when the operator fits, then adding active-block spill or FMM when it does not. This preserves the investment in compressed assembly and avoids committing immediately to dense quadratic disk storage and cubic factor work. Out-of-core dense and distributed direct solvers remain legitimate options where direct-solve robustness and multiple right-hand sides justify their cost.

Measured additions unavailable to Claude's code-only assessment:

- The specified metal inlets pass at 10 GHz with 1.31–1.73 GiB sampled RSS.
- The specified high-contrast material-filled inlet passes at 1 GHz; a stronger inverse approximation reduces median time by 35.4%, with nearly unchanged peak RSS and unchanged quality gates.
- Reducing angle batches from 256 to 64 saves about 250 MiB on the scaled airfoil for about 1.46 seconds additional time.
- All compared fields agree within 9.59e-12 when normalized by their reference peak; all ten cases pass the solver's quality and mesh checks.

These support targeted improvements and further qualification, rather than universal size/frequency cutoffs or removal of accuracy checks.
