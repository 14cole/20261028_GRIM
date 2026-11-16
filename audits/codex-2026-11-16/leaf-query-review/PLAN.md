# Review plan before fresh measurements

Read Claude b9723f3750abed95705ce933241ee2a65c3c6e88 report and audit source.
This is informed reproduction, not a blind review. No production edits.

1. Independently measure dense BlockRow gathers over growing partner widths
   and query sizes. Compare exact values and allocation with a direct
   two-dimensional gather. Preserve None, repeated, reordered and empty
   selection behavior, including the low-rank path.
2. Fresh matched 690 MiB multilayer timing pairs, production / corrected
   sequential / corrected sequential / production, 180 monostatic angles.
   No tracing or archival/other numerical work during these runs.
3. Fresh whole-build allocation audits with production order, original query
   and direct gather, then corrected sequential with direct gather. Trace
   leaf coefficient-query growth separately from cumulative live allocations.
   Keep every solve/condition gate and compare full arrays to fresh Dense.
4. Inspect global admission margins. Do not equate a global physical reserve
   with correct per-query accounting or claim an OOM from a tracer shortfall.
5. Publish measured results, narrow conclusions, complete evidence and an
   independent-review handoff. The query optimization remains research until
   reviewed; do not promote the sequential builder or change defaults here.

Before audit solves, add a fourth audit case with explicit HMatrix diagonal-query pricing (4*q + 1 MiB), alongside direct gather. Full-query synthetic tests will check 149/512/1024 sizes after the timed suite. No generic-oracle workspace claim is made.

Additional capacity follow-up, predicted before running: at 650 MiB production should reject even the compact retry, whereas sequential should admit its ~170.69 MiB compact inverse. This tests the report's overly broad assertion of identical behavior outside the clean-build window. Preserve the expected failed production case.
