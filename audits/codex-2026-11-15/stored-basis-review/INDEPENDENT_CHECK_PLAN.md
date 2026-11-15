# Independent checks before reading Claude's new conclusions

Context: prior right-preconditioned block GMRES applies M to each Arnoldi basis
block, but constructs the candidate with M(VY) instead of storing Z=M(V) and
using ZY. The prior response explicitly noted the fixed-linear-preconditioner
assumption. The new commit's file listing includes a stored-Z variant; I have
seen that listing but have not yet read the new report or results.

Competing hypotheses to test independently:
1. The computed action M is not sufficiently distributive in floating point:
   M(VY) differs from M(V)Y even when M is mathematically fixed and linear.
   A badly scaled approximate inverse can amplify this discrepancy. Stored Z
   preserves the actions used to build Arnoldi and may close the residual gap.
2. Loss in block deflation/Arnoldi or least-squares evaluation causes the gap.
   Storing Z alone would then not consistently fix it.
3. Some restarts are ordinary iteration-cap exhaustion, especially at 32k;
   these should be distinguished from premature projected convergence.

Tests: inspect actual preconditioner arithmetic; construct an independent
controlled floating-point non-distributivity example; compare unmodified old
and new research solvers with true residuals against a dense reference; run
matched physical controls with unchanged accuracy gates, meshes and threads.
Compare accepted solutions, actual operator work, time and peak memory, not
only projected residuals. Preserve complete arrays and failed runs. Label
Claude's large runs separately from fresh local runs.

After these checks, cross-analyze Claude's diagnosis, code and raw evidence.
Agreement alone is not validation. No production change is authorized by
experimental speed alone, and no new relaxed accuracy target is presumed.
