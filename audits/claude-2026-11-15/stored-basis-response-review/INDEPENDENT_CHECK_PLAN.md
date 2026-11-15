# Independent check plan (written before running any check for this round)

Written after reading Codex's handoff `HANDOFF_STORED_BASIS_REVIEW.md` (27afe8f)
once, and before opening its scripts, JSON evidence or diagnostic code. So this
is not blind to Codex's conclusions, only to its method and data.

Claims that matter and how I will test each with my own code:

1. "The retained inverse is double precision." Walk the retained inverse object
   myself and list array dtypes; also read the apply path for any lower
   precision temporaries or casts.
2. "M(VY) differs from ZY by about 3e-11 relative." Measure the additivity
   defect of the retained inverse directly, without any Krylov solver:
   `M(u+v) - M(u) - M(v)` for random vectors, and for the actual scenario.
3. Where the roundoff is amplified. Competing hypotheses:
   - H1: generic cancellation inside the inverse apply (intermediate vectors
     much larger than the result), so the defect appears for any input at
     about (intermediate/result) x 1e-16.
   - H2: the defect is input-specific: the correction VY is a combination with
     large coefficients and heavy cancellation, so it is the *sum* that loses
     digits, and M itself is accurate to ~1e-15 on random inputs.
   - H3: a lower-precision or non-deterministic step in the apply path
     (casts, threaded reductions).
   Test: random-input additivity (H1 vs H2), size of ||Y|| and of the largest
   term |Z_j y_j| against ||ZY|| (H2), repeat-call bitwise determinism and
   dtype trace (H3), and intermediate norms per level if H1 holds.
4. Codex's proposal to replay `M(V_j) y_j` blockwise instead of storing Z:
   implement and measure work, time, memory and accuracy at 8k.
5. Full 32k/180 stored-Z sweep, to replace the 24-angle probe by a measurement.
6. Publish the remaining full arrays in parts below 100 MB.
