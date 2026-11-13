# Solver methods: what can change capacity, and what cannot

This is a research assessment for GHOST's two-dimensional, complex Helmholtz Galerkin solver. Measurements and prototype limitations are in `HANDOFF_SOLVER_METHODS_RESEARCH.md`. Literature results below are not performance claims for GHOST. In particular, 3-D surface-discretization complexity exponents cannot be transferred directly to a 2-D boundary curve.

## FMM: the strongest architectural candidate for operator memory

A dense matrix stores every interaction. FMM groups well-separated sources, represents their fields by expansions, translates those expansions through a spatial tree, and evaluates nearby interactions directly. The resulting operation is an approximation to `y = A x`. It does not factor A, determine x, certify the mesh, or fix a poorly conditioned formulation. Krylov iteration and a preconditioner still perform those jobs.

The official [FMM2D documentation](https://fmm2d.readthedocs.io/en/latest/) describes adaptive trees, vectorized strengths and diagonal translations for high-frequency Helmholtz. Its small-problem advice favors repeated dense BLAS products below roughly 1,000 source/target points. We used the [pinned source](https://github.com/flatironinstitute/fmm2d/tree/7e7509ecd6ebe31b9292cb00825410b478f44808) to determine the actual ABI and normalization because the online overview is older and contains inconsistencies. This library is a kernel evaluator, not a ready-made GHOST backend.

Our Galerkin construction is:

- Spread a density to quadrature points using weighted basis functions Q.
- Evaluate point charges/dipoles/gradients through FMM.
- Gather back to the test basis with Q transpose.
- Replace the naive near/self quadrature contribution with the existing accurately integrated local panel blocks.
- Construct the hypersingular W operator through the tangential-derivative/Maue identity, using single-layer evaluations and normals. This avoids direct pointwise Hessians for W.

With eight quadrature points per panel, 16,000 P1 panels require about 128,000 FMM source points **per interface kernel**, not 128,000 physical unknowns. A two-density transmission formulation then has roughly 32,000 unknowns. Multiple media require different wavenumbers and appropriate restrictions to each region's boundaries. Coincident endpoints, close coatings, corner quadrature, open-interface jump terms, and thin-layer mass inverses must retain their existing treatment. A successful free-space charge test is insufficient evidence for those cases.

The research bridge converts FMM2D's `+i/4 H_0^(1)` result to GHOST's `+i/4 H_0^(2)` with a negative conjugate and conjugated wavenumber/strengths. Omitting the minus sign, prefactor, or loss convention creates incorrect physics even if GMRES converges. Normal, transpose and adjoint identities need independent tests; the current FMM prototype is not connected to the production condition estimator.

### Why an FMM product is not the same as a fast solve

A useful cost model is:

`setup + preconditioner construction + angles × iterations × (FMM product + preconditioner application + orthogonalization) + validation + far field`.

For many angles, factorization reuse can make Dense or the current compressed inverse faster. The existing sweep compression already reduces some right-hand-side work; an FMM implementation must compare against that behavior rather than an artificially naive baseline. Block or recycled GMRES can reuse information across incident angles, but increases storage and must check every reconstructed physical residual. Frequency sweeps can reuse geometry and near lists; translation coefficients and a frequency-sensitive preconditioner generally need updating.

The ctypes entry point used here builds its tree inside each call. A reusable geometry/translation plan and fused S/K/K'/W evaluations are therefore concrete optimization candidates. Multiple strengths amortize traversal work but their expansion storage grows with batch size. Batch all angles blindly and the RAM problem can reappear inside FMM.

RAM also includes the preconditioner, near corrections, quadrature maps, work arrays and Krylov basis. A complex128 GMRES basis of 100 vectors at 100,000 unknowns alone costs about 153 MiB; 32 independent copies cost about 4.8 GiB before other data. Flexible GMRES can retain an additional preconditioned basis. A low-memory operator combined with an expensive hierarchical inverse can still exceed the memory budget.

## Wideband, directional H² and butterfly methods

[Börm's directional H² work](https://arxiv.org/html/1510.07087v5) factors out directional plane-wave oscillations and shares nested cluster bases. Its admissibility includes both ordinary geometric separation and a frequency-dependent condition proportional to `k × diameter² / distance`. The reported storage advantages arise from sharing bases, not just selecting a smaller rank independently for every block. The paper's numerical examples and explicit complexity bounds concern 3-D Helmholtz surfaces; they motivate a 2-D implementation study, not an equivalent capacity forecast.

For GHOST this suggests two alternatives: a kernel-specific wideband FMM, or a directional/nested matrix representation that can still support algebraic preconditioner construction. Both address rank growth that tighter tolerances or more threads cannot remove. Replacing HODLR with another format is a substantial architectural change: inverse compression, near/far admission, transpose actions, memory accounting and failure recovery all change.

[Directional FFT-accelerated interpolation FMM](https://arxiv.org/abs/2202.04894) is another relevant family. It combines directional treatment with equispaced interpolation and FFT acceleration and studies nonuniform BIE particle distributions. That is worth comparing if native FMM2D is limited at high electrical size. It is not implemented or benchmarked here. Butterfly representations similarly exploit oscillatory structure, but would require a separate accuracy and integration study; there is no measured GHOST benefit to quote.

A 20-foot span is 40.7 free-space wavelengths at 2 GHz, 305.0 at 15 GHz and 366.0 at 18 GHz. Those are lengths across the object, not its boundary perimeter. A dielectric with relative permittivity near four roughly doubles the internal electrical length. High-frequency capability must therefore be measured at fixed physical geometry while increasing frequency and maintaining mesh resolution, not solely at fixed frequency while increasing point count.

## Preconditioning and formulation are equally important

The practical first comparison is FMM plus the existing hierarchical inverse, followed by a cheaper near-field/block preconditioner. The former isolates the operator-storage benefit but retains much of today's inverse RAM. The latter can be very small yet need many more iterations. Building a sparse preconditioner by extracting entries from a dense reference, as in our small convergence prototype, demonstrates neither matrix-free construction nor large-model capacity.

[OSRC preconditioning of acoustic transmission](https://arxiv.org/html/2104.04609v2) uses approximate surface Dirichlet-to-Neumann maps within a PMCHWT formulation. The paper reports benefits for material contrast, increasing frequency, corners and multiple scatterers. Its sparse surface solves make it an interesting preconditioner family for a matrix-free operator. However, that is a 3-D acoustic study, not a proof for GHOST's 2-D TE/TM two-density formulation, PEC junctions, or coatings. Deriving compatible weak spaces, material factors, surface mass/stiffness terms, complex square-root branches and corner treatment is required.

Calderón-type operator preconditioning is another principled candidate. Composition can regularize mapping-order mismatches, but weak Galerkin products generally require mass/Riesz maps; simply squaring an assembled matrix is not the correct discretization. Extra operator evaluations can erase iteration savings. Keep exact field equations and production acceptance checks while experimenting with these preconditioners.

The [2025 sparse inverse-LU BEM study](https://geometry.caltech.edu/pubs/CSD25.pdf) is relevant to inexpensive, parallel preconditioning. Its strongest results use Laplace/graphics problems and screening. The authors explicitly discuss degrading efficiency as Helmholtz oscillations weaken screening. Their piecewise-constant collocation examples and large speedups cannot be transplanted to high-frequency Galerkin electromagnetic scattering. A local sparse inverse could still be useful in lossy or moderate-frequency regions; it needs its own holdouts. Forming normal equations to use a symmetric method squares conditioning and adds operator work, making it unattractive here.

The refused 20-foot thin-coated star remains a separate formulation/conditioning problem. FMM changes the cost of evaluating the same equations, not their condition number. A different scaling can change the reported scaled condition number without improving physical accuracy. Any coating reformulation must be assessed with mesh refinement, independent fields, geometry-scale invariance and the original physical residuals. Raising the condition gate is not a remedy.

## Mixed precision: targeted storage, not wholesale float32

[Carson, Chen and Liu](https://arxiv.org/html/2407.21637v5) analyze adaptive-precision HODLR storage and arithmetic. Their precision choices depend on approximation tolerance, level and block magnitudes. This supports selective precision, not blanket complex64 storage for a matrix expected to meet a 1e-12 error budget. Single precision has unit roundoff around 6e-8.

Our experiment instead reduces selected low-rank **inverse/preconditioner** factors, retains leaf and Woodbury LU factors in complex128, keeps the accurate operator, and preserves physical/scaled residual gates. Iterative refinement may recover accuracy from a weaker inverse. It can also stagnate, require rebuilds, or lose any time benefit through conversions. This implementation converts factors after their full-precision construction: retained factor bytes can fall while construction peak RAM stays the same. A production implementation must allocate low-precision storage during construction and account for temporary casts and fallback peaks.

Scaling the inverse construction to match the condition-scaled operator is another experiment. It can change which blocks compress well; algebraically equivalent systems do not necessarily yield smaller factors. The physical solve transforms are `A^-1 = C (RAC)^-1 R`, with R/C swapped for transpose and adjoint actions when the scales are real. Retaining exact external residual checks is essential. Results determine whether this is worth promoting; conditioning intuition alone does not.

## Loss, geometry and alternative approaches

[Variable-order directional H² for complex frequencies](https://arxiv.org/abs/1903.02803) makes attenuation explicit in admissibility and expansion order. Stronger decay can reduce interaction cost and, under the paper's conditions, permit a near-field approximation. Our inference is to investigate material-specific dropping/error bounds for strongly lossy interior regions. The exterior free-space problem still has long-range interactions; a lossy coating does not justify deleting all exterior far fields.

Geometry-aware meshing and higher-order bases can reduce unknown count for a target field error, offering quadratic Dense-storage savings. They change approximation quality, so compare at equal verified accuracy rather than equal panels per wavelength. Corners, gaps and layer thicknesses still need resolution. Combining coplanar geometry segments or replacing thin material by an impedance model can be useful only when the geometric or physical approximation is justified; it is not a universally safe cleanup.

Disk-backed original matrices are already useful for the Dense residual path. Truly out-of-core LU could increase capacity further but still performs cubic arithmetic and moves large tiles through storage; it is a capacity fallback rather than a guaranteed speedup. Memory-mapping a dense matrix and letting it page is not an out-of-core factorization algorithm. No new out-of-core LU was implemented here.

GPU acceleration can improve kernel products or block algebra but requires appropriate double-precision throughput, adequate device RAM, batched transfers, and a CPU fallback. No GPU measurements were made. High-frequency asymptotic/physical-optics models can be much cheaper for selected observables but change the model and can miss diffraction, resonances or interactions. They should be explicit approximation modes with separate validation, not silent replacements for the current BIE.

## A practical development order

1. Decide the Dense refinement target from measured time/accuracy tradeoffs; keep the final acceptance gates and version reference baselines.
2. Qualify selective preconditioner precision, including construction peak memory, transpose/adjoint actions, hard lossless shapes, retries and cancellation.
3. Build an FMM operator interface with reusable plans, correct near corrections, independent residual checks and bounded RHS batches. Compare both sparse and hierarchical preconditioners.
4. Extend through both polarizations, multiple regions, coatings, sheets, open interfaces and higher-order elements; run mesh-converged high-frequency full solves.
5. Investigate OSRC/Calderón or directional nested representations where iteration count or high-frequency rank growth still dominates.

The product can still present one Automatic solver workflow. Dense, compressed and eventually FMM can be internal engines selected from problem size, material, frequency, requested angles and measured resource forecasts. The evidence does not support deleting Dense or declaring a single numerical engine universally best.

## Specific gaps in this FMM prototype

The near-list constructor uses a global maximum panel length to query candidate neighbors and then filters pairwise. Strongly graded meshes can make that search unnecessarily broad, potentially quadratic, even when the accepted list is small. Its Python lists also have a construction peak not represented by the reported retained sparse-array byte count. A production implementation needs bounded buffers and a dual-tree/local-radius search, plus a measured near-field admission model.

The initial full-system adapter supplied the wrong normal orientation, and its subsequent TE material-side mapping was also inconsistent. Independent cylinder checks exposed both errors even though its FMM products matched matrices assembled with the same inconsistent inputs. The failed runs are retained separately. Final physical experiments use inward normals, dielectric on the plus side, and the corresponding `1/eps_r` TE factor. This is evidence for keeping analytic and mesh-refinement tests in the acceptance suite, not evidence of a defect in the unchanged production formulations.
