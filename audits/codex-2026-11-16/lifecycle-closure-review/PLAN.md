# Closure review plan

Read the pinned Claude report and attribution scripts before this plan.
No new solver run is warranted merely to reconfirm the accepted lifecycle fix.

1. Verify all 17 new artifacts and the older star control by Git/array hashes.
2. Recompute saved residual differences and all six original/fixed array-hash
   comparisons; distinguish raw-array replay from hash-only claims.
3. Independently reassemble the 96 star coefficient rows at assembly counts
   1, 2, 3 and 4, with repeats. Cross assembly 1/4 with BLAS 1/4, explicitly
   limit and read back actual loaded BLAS pools inside the computation scope.
   Compare complete exact matrices in memory and preserve sparse coefficient
   differences, complete residuals, norms and hashes for review.
4. Inspect the query path for an explanation without claiming a specific native
   kernel cause unless isolated. Thread dependence does not by itself prove a
   race or an accuracy failure. Do not extrapolate one geometry to all assembly.
5. Keep the accepted production repair unchanged. Publish closure and any
   remaining evidence qualifications; prioritize substantive integration work
   over another cycle of unchanged-solver reruns.
