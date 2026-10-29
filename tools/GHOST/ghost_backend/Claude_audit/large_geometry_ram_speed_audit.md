# Large 2D geometries: RAM and speed audit

Date: 2026-10-29
Scope: GHOST 2D solver code (commit `7a853d8`), the airfoil trial, Codex's 12 ft forecasts and benchmark, and `NUMERICAL_METHODS.md` / `PERFORMANCE_AUDIT_20261024.md`. Code reading and arithmetic only; nothing was run.

## Short answers

1. **Can it handle a 12 ft x 3 ft body with a concave inlet?** It depends far more on the materials than on the shape. A PEC or impedance-boundary (IBC) body is easy at every frequency in the trial range: under about 10,000 unknowns at 10 GHz. A body fully coated with a moderate RAM (refractive index about 4) fits a 16 GB desktop to about 2 to 3 GHz, and needs HPC memory above that. A body coated with the airfoil's high-index material (index about 19) is out of reach of every method in the code above about 1 GHz.
2. **Does the concave inlet itself cause trouble?** Not for the formulation: the integral equations, thin-gap and acute-corner quadrature, and the CFIE all handle concave shapes. The risks are numerical: cavity resonances can trip the condition-number gate (1e6), and facing duct walls drive up compression ranks and the dense near-field share.
3. **Can it work in chunks when RAM is too small?** Partly today: the original matrix, the other polarization and the angle batches can already go to disk or be split. What is missing is a solver that keeps the *factor* out of RAM. An out-of-core tiled LU (desktop) or a distributed LU (HPC) is the most direct fix. A fast-multipole iterative solver is the long-term fix.

## Why size hurts: where RAM goes

| Backend | What grows | Scaling with unknowns N | Example |
| --- | --- | --- | --- |
| Dense / HODLR | Full N x N complex matrix (16 bytes per entry), plus LU copy or HODLR factor | about 27 bytes x N^2 | 127k unknowns: 415 GiB |
| Compressed (H-matrix) | Low-rank blocks; rank of each block grows with its electrical size (12 + 0.21 kD per density, `compressed/hmatrix.py:767`) | Near N log N when electrically small; heads toward N^2 when electrically large | 127k: 132 GiB forecast, only 3x below dense |

The second row is the key limit for 12 ft work. With standard H-matrix admissibility, block ranks in 2D grow in proportion to cluster size in wavelengths. So when the frequency or length goes up at fixed points per wavelength, storage climbs back toward N^2. `NUMERICAL_METHODS.md` measured this already: list ranks of 145 at 2,500 unknowns per cluster and 265 at 5,000, with coarse levels keeping about 14% of N^2. Compression buys a constant factor (3x to 9x), not a different growth rate.

## The 12 ft x 3 ft inlet body

Assumed shape: a 144 x 36 in body with an inlet duct about 5 ft deep. That gives about 480 in of boundary in total (about 360 in outside, 120 in of duct walls).

The unknown counts come from the code's own meshing rule (20 panels per local wavelength, `twod/constants.py`), calibrated against the airfoil. The trial's local P1 mesh at 10 GHz had 28,460 unknowns on 23.7 in of boundary, which matches about 4 unknowns per panel x 20 panels per wavelength x the index-18 material. Adaptive P3 meshing used about 0.4x the unknowns of local P1 in the trial.

| Body | 1 GHz | 3 GHz | 10 GHz |
| --- | --- | --- | --- |
| PEC or IBC everywhere | about 800 | about 2,400 | about 8,000 |
| RAM coating, index about 4, on all surfaces (adaptive) | about 5,000 | about 16,000 | about 52,000 |
| Airfoil-grade material (index about 19) on all surfaces (adaptive) | about 24,000 | about 72,000 | about 240,000 |

A real inlet is usually a PEC outer skin with a coated duct, which lands between the first two rows.

What fits where, using the trial and Codex's measurements:

| Unknowns | 16 GB desktop (8 GiB budget) | Notes |
| --- | --- | --- |
| up to about 17,000 | Dense or compressed | Dense fastest under about 6,000 |
| about 17,000 to 30,000 | Compressed only | Measured: 28,466-unknown airfoil, 100 s, 2.5 GB; 40,000-unknown PEC cylinder, 387 s, 8.5 GB |
| about 30,000 to 60,000 | Refused at 8 GiB; runs on HPC with 32 to 64 GB | The compressed forecast is 2x to 3x high, so some of these would fit if it were tightened |
| above about 60,000, electrically large | Nothing in the code is practical | Needs one of the strategies below |

So a PEC inlet body is easy. A coated inlet works on the desktop up to about 3 GHz, and up to about 5 to 10 GHz on HPC with compressed. A fully high-index-coated body at full scale needs new methods above about 1 GHz.

### Concave and inlet-specific risks

| Risk | Where in code | Effect | What to do |
| --- | --- | --- | --- |
| Cavity resonances | Condition gate `condition_est_max = 1e6` (`twod/solver.py:1025`) | A deep duct is a physical resonator. Near resonance the condition number can exceed 1e6 and the run is rejected, even if the answer is fine. The airfoil sat at 1.6e4. | Expect occasional rejections near duct cutoff frequencies. Allow a per-run override for cavities, judged by the residual and backward-error gates. |
| Facing duct walls | H-matrix admissibility `min(diam) <= dist` (`hmatrix.py:229`) | Two walls a duct-width apart only allow clusters smaller than that width to compress, so more of the matrix stays dense. Cross-duct blocks also have high rank, like the "halves face each other" case at the inverse root. | Forecast and storage will run higher than for a convex body. Directional compression (strategy 6) helps most here. |
| Inverse rank model | `FORECAST_INVERSE_SLOPE = (.3, .12)` | Calibrated on convex bodies, where only the root has facing halves. A duct has facing parts at many levels, so the forecast may under-predict and the run may fail late instead of being refused early. | Validate the forecast on a duct before trusting it. |
| Thin duct lips and gaps | Thin-gap and acute-corner quadrature exist | Correct, but they add near-field work and grading panels. | No change needed. |

## Savings available now (no new solver needed)

Ranked by payoff over effort.

| # | Change | RAM | Speed | Effort | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | **Store incompressible blocks dense instead of rejecting the solve.** `compress_sampled` (`linalg/hierarchical.py:316`) raises "Off-diagonal rank exceeds N" when a block needs more than half its size, which aborts the whole run. Standard H-matrix practice is to keep that block dense. | Small cost | Avoids failed runs | Small | The 6 GHz trial failures (rank 133 = half of a 266 block) |
| 2 | **Spill the compressed operator to disk instead of failing at the storage cap.** The polarization cache already spools to disk (`compressed/polarization_cache.py`); the tile operator raises `MemoryError` instead. | Cap no longer fatal | Some disk I/O | Small to medium | The 8 GHz P2 trial failures |
| 3 | **Calibrate the compressed memory forecast against measured peaks.** Record forecast and measured RSS per run (as `timing_history.py` already does for time) and correct the forecast. | Unlocks runs refused at 8 to 13 GiB that would fit | none | Medium | Forecast 3.06 GiB, measured 1.34 GiB (12 ft, 1 GHz); 20 trial refusals |
| 4 | **Reuse reciprocity in H-matrix assembly.** H-matrix coefficient queries cost about 3.6 dense entries each with no reciprocal reuse; dense assembly already reuses mirrored tiles (`twod/operators.py:2234`). | none | Up to about 2x in assembly, which dominates compressed time | Medium | `NUMERICAL_METHODS.md` (compressed 1.7 to 2.3x slower in multi-region); Codex's 12 ft run (compressed factor 6 s against dense 25 s, totals equal, so assembly is the gap) |
| 5 | **Mixed precision with the double matrix spooled to disk.** Mixed LU exists (`linalg/refined_lu.py`) but keeps a double copy in RAM, so it saves only about 25%. Spooling that copy (the residual spool already exists) leaves only the single-precision factor resident. | Dense: about 32 to 8 bytes per entry, so 4x | Refinement streams the matrix from disk; batch the right-hand sides | Medium | Dense limit on 8 GiB would rise from about 17,700 to about 32,000 unknowns |
| 6 | **Lower the automatic LU to HODLR switch** from 10,000 to about 6,000 unknowns. | Smaller factor | A few seconds per solve | Trivial | Trial: hierarchical beat dense in 37 of 60 adaptive cases from about 6,000 up |
| 7 | **Use geometric mirror symmetry when present.** 2D only reuses mirrored *tiles* during assembly; it does not split a symmetric body into even and odd halves, as BoR does. | 2 systems of N/2: 2x less matrix RAM, 4x less factor work | Large on symmetric cuts | Medium | Not useful for an asymmetric inlet profile, but free on symmetric sections |
| 8 | **Prefer the adaptive mesh** for large runs. | 2.3 to 2.5x fewer unknowns | 2x or more | Already there | Trial at 10 GHz: compressed 47 s adaptive against 109 s local P1 |

## When RAM is too big for any current method: chunking strategies

Already in the code:

- **Residual spool** (`linalg/residual_spool.py`): moves dense LU's original-matrix copy to disk.
- **Polarization spool** (`compressed/polarization_cache.py`, `retained_storage.py`): keeps one polarization's operator on disk while the other solves.
- **Angle batching and RHS compression** (`linalg/sweep.py`): bounds right-hand-side memory, and solves only the independent directions of a monostatic sweep (rank 38 to 39 of 181 angles in the code's own example).
- **Tile streaming** (`compressed/operator.py`): assembles in 512-unknown tiles.
- **One frequency per process** (sweep and HPC scheduler): frequencies never share RAM.

None of these takes the factor itself out of RAM. Options, in order of payoff for 12 ft work:

| Strategy | How it chunks | RAM | Time at 127k unknowns | Effort | Fit |
| --- | --- | --- | --- | --- | --- |
| A. **Out-of-core tiled LU** | Matrix and factor live on NVMe in 4,000 to 8,000-wide tile columns; only a few columns in RAM at a time (left-looking blocked LU with LAPACK on each tile) | A few GB, any N | About 14 h single node (same flops as dense LU), 258 GB of disk | Medium | Desktop, overnight, exact; good up to about 100k |
| B. **Distributed dense LU on HPC** (ScaLAPACK or SLATE through MPI) | Matrix split across nodes | 415 GiB across, say, 8 nodes x 64 GB | Roughly 15 to 30 min on 8 nodes | Medium to high (MPI plus a compiled library; the HPC driver exists) | Best for 50k to 300k unknowns when exact direct solves are wanted |
| C. **Schur-complement or domain chunks** (for example, inlet duct vs exterior) | Factor each subdomain separately, couple through the interface | Largest subdomain squared, plus the interface | Depends on the split | Medium to high | A natural fit for an inlet: the duct is reused across all angles |
| D. **Cavity and aperture decomposition** (generalized scattering matrix) | Solve the duct once as a network from aperture to aperture; the exterior sees only the aperture | Duct and exterior separately | Big savings on deep ducts | High | Standard for jet inlets |
| E. **Iterative solve with a fast matvec** (H-matrix now, or 2D multilevel fast multipole) plus a block preconditioner | No factor at all | Near N log N with fast multipole | Many iterations near cavity resonances; offset by RHS compression | High | The long-term scalable route for electrically large bodies |
| F. **Directional H-matrix or butterfly compression** | Same direct solver, but block ranks stop growing with frequency | Near N log^2 N | Similar to H-matrix | High | Fixes the root cause of the 132 GiB forecast |

Recommended order for 12 ft work:

1. Items 1 to 3 in the savings table above: small, and they stop runs failing or being refused unnecessarily.
2. Item 4, reciprocal reuse in H-matrix assembly: the largest speed gain for large compressed runs.
3. Strategy A, the out-of-core tiled LU: unlimited size on the desktop with an exact direct solve, accepting long runs.
4. Strategy B on HPC, or C/D for inlets specifically, if 12 ft coated bodies above 3 GHz are routine.
5. Strategy E or F only if electrically huge coated bodies become the main workload.

## Caveats

- The unknown counts for the inlet body are order-of-magnitude estimates from the meshing rule and the airfoil calibration. They depend heavily on which surfaces are coated and on the coating index.
- The thresholds of the desktop and HPC columns come from 1 ft airfoil and PEC cylinder measurements plus one 12 ft measurement, not from a duct geometry.
- Effort ratings are judgments from reading the code, not estimates of developer hours.
