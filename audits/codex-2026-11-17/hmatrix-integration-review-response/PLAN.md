# Review plan

Pinned Claude f364689e47cf16abb4c53bdbbb6160fe4a6a90d0, reviewing production
0be5dc314968ebf31b0165548c81ad9ede0f1bf1. Read the review and independent plan.

1. Verify pinned reviewer scripts and raw JSON/log records by Git identity.
   Cross-check old/new hashes, cap outcomes, allocation and cancellation data.
2. Re-run the extended selector and copy-path tests on actual production.
   Do not repeat the accepted 32k solve merely to close the review.
3. Independently construct a bounded-headroom leaf-query admission check using
   the actual production ledger. Measure the stricter old/new allowance and
   prove rejection happens before querying, with cleanup and recovery. This is
   a controlled admission experiment, not a real RAM-pressure solve.
4. Resolve the README comment against the already-published instructions and
   separate small timing fluctuations from the reproduced capped mechanism.
5. Publish acceptance, any corrections and evidence. No merge or speculative
   performance change; keep platform/64k/operator-memory work separate.
