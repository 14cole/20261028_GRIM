# Further methods and their implications

These are implementation options and evidence-based priorities, not promised production speedups. See the handoff for measured experiments.

## Reusable plans and integrated near interactions

The point FMM should build geometry, interpolation and translation data once for a mesh/wavenumber, then accept new charge vectors during iteration and across angles. The earlier native FMM2D wrapper rebuilds its internal tree each application. Reuse moves that work into setup, but retained plans cost RAM. Material regions with different wavenumbers need distinct translation data even when they share geometry.

A Galerkin panel with q source and q target quadrature nodes creates q² point interactions per panel pair. Keeping exact integrated 2×2 P1 panel blocks in the near field can avoid this q² storage. Our experimental implementation assigns every panel's quadrature nodes to the panel-center leaf, enlarges the expansion support, excludes those complete near panel pairs from the far product, and integrates them using GHOST's native routines. This avoids subtraction of two large approximate near operators. It also turns the near field into a candidate sparse preconditioner. Correct partitioning, signs, material sides, touching-panel integration and target derivatives must all be validated. The prototype rejects panels too large relative to the leaf size and imposes research allocation guards. It is P1-only and assumes a positive real wavenumber with the passive imaginary sign; zero or purely imaginary wavenumbers are not supported. Its demonstration PEC equation is the Dirichlet/TM combined field, not a validation of PEC Neumann/TE or open surfaces.

The current panel-near constructor still holds coefficient construction buffers. Streaming those into CSR and sharing sparse structure can lower setup peaks. Source/target expansion tiles bound application temporaries; retaining all leaf exponentials is another reducible term. A fused system application can share one traversal between S/K and some gradient components, but must be benchmarked for its additional RHS workspace.

## Stable wideband FMM: strongest next architectural investigation

Widening the near stencil cures the measured cancellation in our examples at a storage/setup cost. It does not solve dense geometric clustering: wavelength-sized boxes can contain many panels, and near work can become quadratic with refinement at fixed frequency.

Cho and Cai (2010), *A Wideband Fast Multipole Method for the two-dimensional complex Helmholtz equation*, describe using partial-wave translations at small box wavenumber-size and diagonal translations at larger scales. That permits finer low-frequency leaves without the ordinary diagonal instability. Their published implementation has its own CPC license; the paper is algorithmic evidence, not a redistribution approval or GHOST benchmark. Source: https://doi.org/10.1016/j.cpc.2010.09.010 ; accessible author copy: https://bpb-us-w2.wpmucdn.com/people.smu.edu/dist/e/573/files/2017/12/WidebandFMM.pdf .

Cheng et al. (2006) describe a related 3D wideband scheme. Its low-/high-frequency division supports the architectural rationale, but it is not a drop-in implementation for this 2D solver. Source: https://doi.org/10.1016/j.jcp.2005.12.001 .

A recent, specifically 2D alternative is *A Stable Matrix Version of the Wideband Fast Multipole Method for the 2D Helmholtz Kernel*, DOI 10.1137/24M1712837; author manuscript: https://www.math.purdue.edu/~xiaj/work/fmmhelm.pdf . Its stability analysis makes this worth studying before committing to the present diagonal prototype. Published stability of an algorithm does not certify our different implementation. Its theorem uses stated tree and generator assumptions; the manuscript notes that its bound is not always a relative-error bound, and its numerical examples focus mainly on the low-frequency expansion. It is an especially relevant design reference, not an end-to-end scattering or dielectric benchmark.

The relevant holdouts are locally refined corners, close parallel interfaces, thin coatings, high contrast, lossy material and low frequency at fixed fine mesh. Compare both setup and retained storage as points are doubled at fixed k; near-linear high-frequency scaling alone misses this failure mode. An adaptive tree with balanced near lists and a stable low-frequency representation is the desirable end state. Our geometry-only count experiment at fixed 2 GHz confirms the concern: the star's near panel pairs grow from 1.80 million at 4,000 panels to 7.21 million at 8,000 and 28.82 million at 16,000. Two closely spaced stars with 16,000 panels each require 115.71 million near pairs, implying 27.59 GiB for the prototype's guarded coefficient-construction buffers alone. These are exact pair counts and an allocation formula, not completed solves or a prediction for an adaptive FMM. See `GEOMETRY_NEAR_SCALING.json` in the archive. The research 2 GiB construction and 3 GiB point-near guards protect this 16 GiB test environment; they are not new production limits.

## Preconditioners determine whether the memory win is usable

Cheap products help only if iteration counts remain manageable. A local ILU from integrated near blocks is the first practical control. It adds sparse factor fill and setup, and it can fail or become large for strong coupling. Dense-derived row/column scales in our small tests are explicitly a validation convenience, not a scalable solution.

Beyond that, test block preconditioning by physical interface/material region, and a coarse global correction to capture interactions that a local stencil misses. Reusing the existing Compressed machinery at a looser tolerance as a preconditioner could reduce iteration count, but retains compressed-factor RAM and needs true-residual checks. Operator/Calderón and on-surface radiation condition (OSRC) preconditioning have promising transmission literature. Acoustic PMCHWT results (https://arxiv.org/abs/2104.04609) motivate research, but their equations, spaces and material coefficients must be rederived for GHOST's 2D TE/TM formulation; do not import iteration or speedup claims.

For each candidate, judge setup + every-angle solve time, sparse-factor bytes, peak process RAM, and exact-reference backward error. A preconditioner that reduces iterations but doubles each iteration's work can lose overall.

## Many angles and one user workflow

A shared immutable plan and per-worker bounded scratch are suitable for angle concurrency. For complex128, the Krylov basis alone is approximately 16 * number_of_unknowns * (restart+1) * chunk_columns * workers bytes; dielectric unknowns and multiple interfaces must be counted, not just boundary nodes. Plans, preconditioners, RHS/output arrays and temporary expansions are additional allocations. Treat worker count and chunk size as a joint RAM allocation decision. Independent Krylov spaces still store basis vectors per angle; batching does not eliminate that requirement. Unrestarted GMRES can grow until memory is exhausted, so production requires bounded restart/recycling and explicit convergence failure handling.

Dense and direct Compressed methods amortize their expensive factorization across angles. FMM repeats iterative work. For a fixed problem a useful measured model is T_FMM = setup + n_angles * iteration_cost * iterations / effective_workers; direct time is factorization + n_angles * triangular_or_inverse_apply. Inputs must come from matched discretization and accuracy, and the iteration count can vary by angle. No numerical crossover follows from unlike prototypes.

One user-facing Automatic mode can still route among several internal engines. This avoids asking users to understand FMM internals while preserving direct methods when factor reuse wins. An FMM route should be offered only after certification, cancellation, memory estimates, progress reporting, failure recovery and Windows packaging are ready.

## Lower-priority alternatives

Disk-backed dense LU changes capacity but retains cubic arithmetic and incurs heavy I/O; it is not a substitute for the demonstrated matrix-free memory benefit. Reduced precision is more attractive in a preconditioner than in an unverified final operator. FFT grid methods may help regular geometries, but padding and interpolation become costly for detailed boundaries. Directional H² can share far bases and potentially retain direct multi-angle advantages, at substantially greater factorization implementation complexity. These remain research options; no new measurements for them are claimed here.

## A concrete certification path

Keep three errors separate: quadrature/discretization error, fast-operator approximation error, and iterative solve error. Tightening GMRES only addresses the third. On validation-sized problems, evaluate the final residual with the assembled production operator, compare complex fields and perform analytic/mesh-convergence checks independently.

At large size, a rigorous operator error bound would permit `||b-Ax|| <= ||b-A_approx*x|| + ||A-A_approx||*||x||`. A sampled error from random charges does not supply that bound. Normalizing this residual also requires a trustworthy norm or bound of the appropriately scaled operator. An upper bound on the denominator alone is not conservative for accepting backward error; its direction matters. Production-equivalent condition estimation requires accurate inverse and adjoint-inverse actions, normally additional iterative solves, and an explicit account of their accuracy and cost. Existing estimator-based gates should be matched and validated as such, rather than described as rigorous bounds they do not provide.

A practical development sequence is: implement/test adjoints against dense reference; establish deterministic approximation error controls; implement bounded-memory scaling and norm estimation; audit condition-estimator solves; then validate the final acceptance decision against Dense across both passing and deliberately failing cases. Independent sampled rows remain valuable diagnostics but cannot certify the unexamined rows.
